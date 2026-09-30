import pytest
from threadline.metrics import average_precision_at_k, catalogue_coverage, map_at_k, recall_at_k


def test_perfect_prediction_scores_one():
    assert average_precision_at_k([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_no_hits_scores_zero():
    assert average_precision_at_k([1, 2], [3, 4, 5]) == 0.0


def test_hand_computed_example():
    # hits at positions 1 and 3: (1/1 + 2/3) / min(3, 12)
    assert average_precision_at_k([1, 2, 9], [1, 5, 2, 7]) == pytest.approx((1 + 2 / 3) / 3)


def test_duplicates_count_once():
    assert average_precision_at_k([1], [1, 1, 1]) == pytest.approx(1.0)


def test_truncates_at_k():
    assert average_precision_at_k([13], list(range(1, 14)), k=12) == 0.0


def test_denominator_capped_at_k():
    actual = list(range(20))
    assert average_precision_at_k(actual, actual, k=12) == pytest.approx(1.0)


def test_map_missing_user_scores_zero():
    assert map_at_k({1: [1], 2: [2]}, {1: [1]}) == pytest.approx(0.5)


def test_recall_and_coverage():
    assert recall_at_k({1: [1, 2], 2: [3]}, {1: [1, 9], 2: [3]}) == pytest.approx(2 / 3)
    assert catalogue_coverage({1: [1, 2], 2: [2, 3]}, n_items=10) == pytest.approx(0.3)
