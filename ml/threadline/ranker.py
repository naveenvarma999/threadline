"""Stage 2: learning-to-rank with scikit-learn gradient boosting."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from threadline.features import FEATURES

log = logging.getLogger(__name__)


def train_ranker(train: pd.DataFrame, seed: int = 42, features: list[str] | None = None,
                 **params) -> HistGradientBoostingClassifier:
    """Binary pointwise ranker: label = candidate was bought in the label week."""
    defaults = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=48, min_samples_leaf=40,
                    l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
                    n_iter_no_change=30, random_state=seed)
    defaults.update(params)
    model = HistGradientBoostingClassifier(**defaults)
    # Down-weight negatives so each label week contributes a balanced signal.
    y = train["label"].to_numpy()
    pos_rate = y.mean()
    w = np.where(y == 1, 1.0, pos_rate / (1 - pos_rate) * 5)
    model.fit(train[features or FEATURES], y, sample_weight=w)
    model.feature_list_ = list(features or FEATURES)
    log.info("Ranker trained: %d iterations, %d rows, positive rate %.4f", model.n_iter_, len(train), pos_rate)
    return model


def score(model, cands: pd.DataFrame) -> np.ndarray:
    cols = getattr(model, "feature_list_", FEATURES)
    return model.predict_proba(cands[cols])[:, 1]


def top_k(cands: pd.DataFrame, scores: np.ndarray, k: int = 12) -> dict[int, list[int]]:
    c = cands[["customer_idx", "article_id"]].assign(score=scores)
    c = c.sort_values(["customer_idx", "score"], ascending=[True, False])
    return c.groupby("customer_idx")["article_id"].apply(lambda s: s.head(k).tolist()).to_dict()


def auc(model, df: pd.DataFrame) -> float:
    y = df["label"].to_numpy()
    return float(roc_auc_score(y, score(model, df))) if 0 < y.sum() < len(y) else float("nan")


def importance(model, df: pd.DataFrame, n_rows: int = 30000, seed: int = 0) -> pd.Series:
    """Permutation importance on a sample of held-out rows (AUC drop)."""
    sample = df.sample(min(n_rows, len(df)), random_state=seed)
    cols = getattr(model, "feature_list_", FEATURES)
    r = permutation_importance(model, sample[cols], sample["label"], scoring="roc_auc",
                               n_repeats=3, random_state=seed, n_jobs=1)
    return pd.Series(r.importances_mean, index=cols).sort_values(ascending=False)
