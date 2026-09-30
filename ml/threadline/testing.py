"""Build a tiny but complete model bundle without PyTorch or TensorFlow (for service tests and CI)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from threadline.bundle import save_bundle
from threadline.config import TrainConfig
from threadline.data import generate_synthetic, prepare
from threadline.features import build_features, make_snapshot
from threadline.ranker import train_ranker
from threadline.retrieval import CandidateGenerator, RetrievalModels, build_cooccurrence
from threadline.two_tower import N_AGE_BANDS, TwoTowerNumpy


def _random_two_tower(n_items: int, d: int, rng) -> TwoTowerNumpy:
    v = rng.normal(size=(n_items, d)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return TwoTowerNumpy(
        item_vecs=v, age_emb=rng.normal(size=(N_AGE_BANDS, 8)).astype(np.float32),
        w1=rng.normal(scale=.1, size=(2 * d, d + 10)).astype(np.float32), b1=np.zeros(2 * d, np.float32),
        w2=rng.normal(scale=.1, size=(d, 2 * d)).astype(np.float32), b2=np.zeros(d, np.float32),
    )


def make_tiny_bundle(out: Path, seed: int = 0) -> Path:
    rng = np.random.default_rng(seed)
    cfg = TrainConfig()
    object.__setattr__(cfg, "history_weeks", 8)
    ds = prepare(*generate_synthetic(n_articles=300, n_customers=800, n_weeks=8, seed=seed), cfg=cfg)
    T = ds.last_week
    content = rng.normal(size=(len(ds.articles), 16)).astype(np.float32)
    content /= np.linalg.norm(content, axis=1, keepdims=True)
    tx = ds.transactions[ds.transactions["week"] < T]
    retr = RetrievalModels(_random_two_tower(len(ds.articles), 16, rng), content, build_cooccurrence(tx),
                           ds.articles["article_id"].to_numpy())
    gen = CandidateGenerator(retr, ds.customers.set_index("customer_idx")["age"])
    snap = make_snapshot(ds, T)
    week = ds.transactions[ds.transactions["week"] == T]
    feats = build_features(gen.generate(week["customer_idx"].unique(), snap), snap)
    bought = set(zip(week["customer_idx"], week["article_id"]))
    feats["label"] = [int(p in bought) for p in zip(feats["customer_idx"], feats["article_id"])]
    model = train_ranker(feats, max_iter=30)
    save_bundle(out, articles=ds.articles, customers=ds.customers, snapshot=make_snapshot(ds, T + 1),
                retrieval=retr, ranker=model,
                metadata={"model_name": "threadline-recommender", "data_source": "tiny-test",
                          "metrics": {"test_map12": 0.0}, "ablation": {}, "top_features": {}})
    return out
