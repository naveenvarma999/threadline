"""Ranking metrics, implemented in NumPy so they are fast and easy to test."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def average_precision_at_k(actual: Sequence[int], predicted: Sequence[int], k: int = 12) -> float:
    """AP@k exactly as scored in the H&M competition.

    AP@k = 1/min(m, k) * sum_{i<=k} P(i) * rel(i), where m = number of relevant items.
    Duplicate predictions only count the first time.
    """
    if not actual:
        return 0.0
    actual_set = set(actual)
    seen: set[int] = set()
    hits = 0
    score = 0.0
    for i, p in enumerate(predicted[:k]):
        if p in actual_set and p not in seen:
            hits += 1
            score += hits / (i + 1.0)
        seen.add(p)
    return score / min(len(actual_set), k)


def map_at_k(actual: Mapping[int, Sequence[int]], predicted: Mapping[int, Sequence[int]], k: int = 12) -> float:
    """Mean AP@k over the users in ``actual``. Users with no prediction score zero."""
    if not actual:
        return 0.0
    return float(np.mean([average_precision_at_k(a, predicted.get(u, []), k) for u, a in actual.items()]))


def recall_at_k(
    actual: Mapping[int, Sequence[int]], predicted: Mapping[int, Sequence[int]], k: int | None = None
) -> float:
    """Share of relevant items found in the (optionally truncated) predictions, micro-averaged.

    Used with ``k=None`` to measure candidate recall: the ceiling the ranker can reach.
    """
    found = total = 0
    for u, a in actual.items():
        a_set = set(a)
        preds = predicted.get(u, [])
        p_set = set(preds if k is None else preds[:k])
        found += len(a_set & p_set)
        total += len(a_set)
    return found / total if total else 0.0


def catalogue_coverage(predicted: Mapping[int, Sequence[int]], n_items: int, k: int = 12) -> float:
    """Share of the catalogue that appears in at least one top-k list."""
    items = {i for preds in predicted.values() for i in preds[:k]}
    return len(items) / n_items if n_items else 0.0
