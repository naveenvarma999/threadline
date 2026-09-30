"""Model bundle: everything the inference service needs, in one directory.

The training pipeline writes a bundle, logs it to MLflow as a pyfunc model and registers it.
The inference service downloads the bundle for the ``champion`` alias and wraps it in
``Recommender``, which only needs NumPy, pandas, scikit-learn and (optionally) FAISS.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from threadline.features import Snapshot, build_features
from threadline.ranker import score
from threadline.retrieval import CandidateConfig, CandidateGenerator, RetrievalModels
from threadline.two_tower import TwoTowerNumpy

log = logging.getLogger(__name__)

REASONS = {
    "rep": "You bought this before",
    "cooc": "Often bought with items you chose",
    "tt": "Matches your style",
    "pop": "Trending with shoppers like you",
}
CUSTOMER_COLS = ["customer_id", "customer_idx", "age"]


def save_bundle(
    out: Path,
    *,
    articles: pd.DataFrame,
    customers: pd.DataFrame,
    snapshot: Snapshot,
    retrieval: RetrievalModels,
    ranker,
    metadata: dict,
) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    articles.to_parquet(out / "articles.parquet", index=False)
    customers[CUSTOMER_COLS].to_parquet(out / "customers.parquet", index=False)
    snapshot.save(out / "snapshot")
    retrieval.two_tower.save(out / "two_tower.npz")
    np.save(out / "content_emb.npy", retrieval.content_emb)
    retrieval.cooc.to_parquet(out / "cooc.parquet", index=False)
    joblib.dump(ranker, out / "ranker.joblib")
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
    return out


@dataclass
class Recommendation:
    article_id: int
    score: float
    sources: list[str]
    reason: str


class Recommender:
    """Online scoring: candidates -> features -> ranker -> top-k with explanations."""

    def __init__(self, bundle_dir: Path) -> None:
        t0 = time.perf_counter()
        d = Path(bundle_dir)
        self.metadata = json.loads((d / "metadata.json").read_text())
        self.articles = pd.read_parquet(d / "articles.parquet")
        customers = pd.read_parquet(d / "customers.parquet")
        self.customer_idx = pd.Series(customers["customer_idx"].to_numpy(), index=customers["customer_id"].to_numpy())
        self.customer_age = pd.Series(customers["age"].to_numpy(), index=customers["customer_idx"].to_numpy())
        self.snapshot = Snapshot.load(d / "snapshot", self.articles)
        self.retrieval = RetrievalModels(
            two_tower=TwoTowerNumpy.load(d / "two_tower.npz"),
            content_emb=np.load(d / "content_emb.npy"),
            cooc=pd.read_parquet(d / "cooc.parquet"),
            article_ids=self.articles["article_id"].to_numpy(),
        )
        self.ranker = joblib.load(d / "ranker.joblib")
        self.generator = CandidateGenerator(self.retrieval, self.customer_age, CandidateConfig())
        self.item_price = self.snapshot.item_feats["i_mean_price"]
        self._hist_by_user = self.snapshot.history.groupby("customer_idx")
        self.load_seconds = time.perf_counter() - t0
        log.info("Bundle loaded in %.2fs (%d articles, %d customers)",
                 self.load_seconds, len(self.articles), len(customers))

    # ------------------------------------------------------------------ helpers
    def _history_for(self, idx: int, recent: list[int]) -> pd.DataFrame:
        try:
            h = self._hist_by_user.get_group(idx)
        except KeyError:
            h = self.snapshot.history.iloc[0:0]
        recent = [a for a in recent if a in self.retrieval.row_of.index]
        if recent:
            extra = pd.DataFrame({
                "customer_idx": idx,
                "article_id": np.asarray(recent, dtype=np.int32),
                # newest first, just before the reference date
                "t_dat": [self.snapshot.ref_date - pd.Timedelta(seconds=i + 1) for i in range(len(recent))],
                "price": self.item_price.reindex(recent).fillna(self.item_price.median()).to_numpy(np.float32),
            })
            h = pd.concat([extra, h], ignore_index=True)
        return h

    @staticmethod
    def _sources(row) -> list[str]:
        return [s for s in ("rep", "cooc", "tt", "pop") if row[f"src_{s}"] > 0]

    # ------------------------------------------------------------------ public API
    def recommend(self, customer_id: str | None, k: int = 12, recent_article_ids: list[int] | None = None,
                  age: float | None = None, exclude: list[int] | None = None) -> list[Recommendation]:
        recent = list(recent_article_ids or [])
        idx = int(self.customer_idx.get(customer_id, -1)) if customer_id else -1
        hist = self._history_for(idx, recent)
        age_override = {idx: age} if (idx == -1 and age is not None) else None
        cands = self.generator.generate(np.array([idx]), self.snapshot, history=hist, age_override=age_override)
        if exclude:
            cands = cands[~cands["article_id"].isin(exclude)]
        feats = build_features(cands, self.snapshot, history=hist)
        feats["score"] = score(self.ranker, feats)
        top = feats.sort_values("score", ascending=False).head(k)
        out = []
        for _, r in top.iterrows():
            src = self._sources(r)
            out.append(Recommendation(int(r["article_id"]), float(r["score"]), src,
                                      REASONS[src[0]] if src else REASONS["tt"]))
        return out

    def similar(self, article_id: int, k: int = 12) -> list[tuple[int, float]]:
        row = self.retrieval.row_of.get(article_id)
        if row is None:
            return []
        c = self.retrieval.content_emb
        t = self.retrieval.two_tower.item_vecs
        s = 0.5 * (c @ c[row]) + 0.5 * (t @ t[row])
        s[row] = -np.inf
        top = np.argpartition(-s, k)[:k]
        top = top[np.argsort(-s[top])]
        return [(int(self.retrieval.article_ids[i]), float(s[i])) for i in top]

    def bought_together(self, article_id: int, k: int = 6) -> list[tuple[int, float]]:
        g = self.retrieval.cooc_map.get(article_id)
        if g is None:
            return []
        return [(int(a), float(s)) for a, s in g.head(k).itertuples(index=False)]

    def popular(self, k: int = 12, age: float | None = None) -> list[int]:
        from threadline.features import age_band

        if age is not None:
            return self.snapshot.popular.get(int(age_band([age])[0]), self.snapshot.popular_global)[:k]
        return self.snapshot.popular_global[:k]
