"""Stage 1: candidate retrieval.

Four retrievers each propose articles; their union (typically 100-150 per user) goes to the
ranker together with per-source flags and ranks, so the ranker can learn how much to trust
each source.

* popularity : best sellers of the last week in the user's age band (the baseline to beat)
* repurchase : the user's own recent purchases (basics get bought again)
* co-purchase: items bought in the same week by the same customers as the user's recent items
* two-tower  : nearest neighbours of the user vector in the item vector space (FAISS)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from threadline.features import Snapshot, age_band
from threadline.two_tower import TwoTowerNumpy

log = logging.getLogger(__name__)
MISSING_RANK = 999.0


def build_cooccurrence(tx: pd.DataFrame, max_basket: int = 20, top_n: int = 20, min_count: int = 2) -> pd.DataFrame:
    """Item-to-item scores from same-customer, same-week baskets.

    score(a -> b) = count(a, b) / (count(a) + 10): a smoothed P(b | a).
    """
    b = tx[["customer_idx", "week", "article_id"]].drop_duplicates()
    b = b.groupby(["customer_idx", "week"]).head(max_basket)
    b = b.assign(basket=b.groupby(["customer_idx", "week"]).ngroup())[["basket", "article_id"]]
    pairs = b.merge(b, on="basket", suffixes=("", "_nb"))
    pairs = pairs[pairs["article_id"] != pairs["article_id_nb"]]
    counts = pairs.groupby(["article_id", "article_id_nb"]).size().rename("n").reset_index()
    counts = counts[counts["n"] >= min_count]
    item_n = b.groupby("article_id").size()
    counts["score"] = counts["n"] / (counts["article_id"].map(item_n) + 10)
    counts = counts.sort_values(["article_id", "score"], ascending=[True, False])
    out = counts.groupby("article_id").head(top_n)
    return out.rename(columns={"article_id_nb": "neighbor"})[["article_id", "neighbor", "score"]].reset_index(drop=True)


class VectorIndex:
    """Exact inner-product search. Uses FAISS when installed, NumPy otherwise."""

    def __init__(self, vectors: np.ndarray) -> None:
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        try:
            import faiss

            self._faiss = faiss.IndexFlatIP(self.vectors.shape[1])
            self._faiss.add(self.vectors)
        except ImportError:
            self._faiss = None

    def search(self, queries: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        q = np.ascontiguousarray(queries, dtype=np.float32)
        if self._faiss is not None:
            return self._faiss.search(q, k)
        scores = q @ self.vectors.T
        idx = np.argpartition(-scores, kth=min(k, scores.shape[1] - 1), axis=1)[:, :k]
        top = np.take_along_axis(scores, idx, axis=1)
        order = np.argsort(-top, axis=1)
        return np.take_along_axis(top, order, axis=1), np.take_along_axis(idx, order, axis=1)


@dataclass
class RetrievalModels:
    two_tower: TwoTowerNumpy
    content_emb: np.ndarray  # (n_items, c), rows aligned with articles
    cooc: pd.DataFrame
    article_ids: np.ndarray  # row -> article_id

    def __post_init__(self) -> None:
        self.row_of = pd.Series(np.arange(len(self.article_ids)), index=self.article_ids)
        self.tt_index = VectorIndex(self.two_tower.item_vecs)
        self.content_index = VectorIndex(self.content_emb)
        self.cooc_map = {a: g for a, g in self.cooc.groupby("article_id")[["neighbor", "score"]]}


@dataclass
class CandidateConfig:
    n_popular: int = 30
    n_repurchase: int = 20
    n_cooc: int = 40
    n_two_tower: int = 50


class CandidateGenerator:
    def __init__(self, models: RetrievalModels, customer_age: pd.Series, cfg: CandidateConfig | None = None) -> None:
        self.m = models
        self.customer_age = customer_age
        self.cfg = cfg or CandidateConfig()

    def _ages(self, users: np.ndarray, age_override: dict[int, float] | None) -> np.ndarray:
        ages = self.customer_age.reindex(users)
        if age_override:
            ages = ages.fillna(pd.Series(age_override))
        return ages.fillna(self.customer_age.median()).to_numpy()

    def user_vectors(self, users: np.ndarray, hist: pd.DataFrame, snap: Snapshot,
                     age_override: dict[int, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
        rows_by_user = hist.assign(row=self.m.row_of.reindex(hist["article_id"]).to_numpy()).dropna(subset=["row"])
        grouped = rows_by_user.groupby("customer_idx")["row"].apply(lambda s: s.astype(int).tolist()[:20])
        hist_rows = [grouped.get(u, []) for u in users]
        ages = self._ages(users, age_override)
        online = snap.user_feats["u_online_ratio"].reindex(users).fillna(0.5).to_numpy()
        u_tt = self.m.two_tower.encode_users(hist_rows, age_band(ages), online)
        c = self.m.content_emb.shape[1]
        u_content = np.zeros((len(users), c), dtype=np.float32)
        for i, rows in enumerate(hist_rows):
            if rows:
                v = self.m.content_emb[rows].mean(0)
                u_content[i] = v / (np.linalg.norm(v) + 1e-8)
        return u_tt, u_content

    def generate(self, users: np.ndarray, snap: Snapshot, history: pd.DataFrame | None = None,
                 age_override: dict[int, float] | None = None) -> pd.DataFrame:
        cfg = self.cfg
        users = np.asarray(users)
        hist = (snap.history if history is None else history)
        hist = hist[hist["customer_idx"].isin(users)].sort_values("t_dat", ascending=False)
        parts = []

        # popularity by age band
        bands = age_band(self._ages(users, age_override))
        pop_rows = []
        for u, b in zip(users, bands):
            lst = snap.popular.get(int(b), snap.popular_global)[: cfg.n_popular]
            pop_rows.extend((u, a, r) for r, a in enumerate(lst))
        parts.append(pd.DataFrame(pop_rows, columns=["customer_idx", "article_id", "rank_pop"]))

        # repurchase
        rep = hist.drop_duplicates(["customer_idx", "article_id"]).groupby("customer_idx").head(cfg.n_repurchase)
        rep = rep.assign(rank_rep=rep.groupby("customer_idx").cumcount())[["customer_idx", "article_id", "rank_rep"]]
        parts.append(rep)

        # co-purchase from the user's 10 most recent distinct items, recency-weighted
        recent = hist.drop_duplicates(["customer_idx", "article_id"]).groupby("customer_idx").head(10)
        recent = recent.assign(w=0.9 ** recent.groupby("customer_idx").cumcount())
        nb = recent.merge(self.m.cooc, on="article_id")
        if not nb.empty:
            nb = nb.assign(s=nb["score"] * nb["w"]).groupby(["customer_idx", "neighbor"])["s"].sum().reset_index()
            nb = nb.sort_values(["customer_idx", "s"], ascending=[True, False]).groupby("customer_idx").head(cfg.n_cooc)
            nb = nb.assign(rank_cooc=nb.groupby("customer_idx").cumcount())
            parts.append(nb.rename(columns={"neighbor": "article_id", "s": "cooc_score"})
                         [["customer_idx", "article_id", "rank_cooc", "cooc_score"]])

        # two-tower ANN
        u_tt, u_content = self.user_vectors(users, hist, snap, age_override)
        _, idx = self.m.tt_index.search(u_tt, cfg.n_two_tower)
        parts.append(pd.DataFrame({
            "customer_idx": np.repeat(users, idx.shape[1]),
            "article_id": self.m.article_ids[idx.ravel()],
            "rank_tt": np.tile(np.arange(idx.shape[1]), len(users)),
        }))

        c = pd.concat(parts, ignore_index=True)
        for col in ("rank_pop", "rank_rep", "rank_cooc", "rank_tt", "cooc_score"):
            if col not in c:
                c[col] = np.nan
        agg = c.groupby(["customer_idx", "article_id"], sort=False).agg(
            rank_pop=("rank_pop", "min"), rank_rep=("rank_rep", "min"),
            rank_cooc=("rank_cooc", "min"), rank_tt=("rank_tt", "min"),
            cooc_score=("cooc_score", "max"),
        ).reset_index()
        agg = agg[agg["article_id"].isin(self.m.row_of.index)]
        for src in ("pop", "rep", "cooc", "tt"):
            agg[f"src_{src}"] = agg[f"rank_{src}"].notna().astype(np.float32)
            agg[f"rank_{src}"] = agg[f"rank_{src}"].fillna(MISSING_RANK)
        agg["cooc_score"] = agg["cooc_score"].fillna(0)

        # dense scores for every candidate
        upos = pd.Series(np.arange(len(users)), index=users)
        ui = upos.reindex(agg["customer_idx"]).to_numpy()
        rows = self.m.row_of.reindex(agg["article_id"]).to_numpy()
        agg["tt_score"] = np.einsum("ij,ij->i", u_tt[ui], self.m.two_tower.item_vecs[rows])
        agg["content_sim"] = np.einsum("ij,ij->i", u_content[ui], self.m.content_emb[rows])
        return agg

    def source_ranking(self, cands: pd.DataFrame, source: str, k: int = 12) -> dict[int, list[int]]:
        """Top-k per user ordered by a single retriever's own rank (for baselines/ablations)."""
        c = cands[cands[f"src_{source}"] > 0].sort_values(["customer_idx", f"rank_{source}"])
        return c.groupby("customer_idx")["article_id"].apply(lambda s: s.head(k).tolist()).to_dict()
