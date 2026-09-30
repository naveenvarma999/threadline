"""Leakage and consistency tests for point-in-time features."""

import numpy as np
from threadline.features import FEATURES, build_features, make_snapshot


def test_snapshot_never_sees_the_reference_week(small_ds):
    ref = small_ds.last_week
    snap = make_snapshot(small_ds, ref)
    assert snap.history["t_dat"].max() < snap.ref_date
    ref_week_tx = small_ds.transactions[small_ds.transactions["week"] == ref]
    assert ref_week_tx["t_dat"].min() >= snap.ref_date


def test_item_sales_match_manual_count(small_ds):
    ref = small_ds.last_week
    snap = make_snapshot(small_ds, ref)
    past = small_ds.transactions[small_ds.transactions["week"] < ref]
    article = past["article_id"].value_counts().index[0]
    assert snap.item_feats.loc[article, "i_sales_all"] == (past["article_id"] == article).sum()


def test_future_purchases_do_not_change_features(small_ds):
    """Adding transactions in the reference week must not change any feature value."""
    ref = small_ds.last_week - 1
    snap_a = make_snapshot(small_ds, ref)
    tx = small_ds.transactions
    ds_b = type(small_ds)(tx[tx["week"] < ref + 1], small_ds.articles, small_ds.customers)
    snap_b = make_snapshot(ds_b, ref)
    assert snap_a.ref_date == snap_b.ref_date
    np.testing.assert_allclose(snap_a.user_feats.sort_index().to_numpy(), snap_b.user_feats.sort_index().to_numpy())
    np.testing.assert_allclose(snap_a.item_feats.sort_index().to_numpy(), snap_b.item_feats.sort_index().to_numpy())


def test_build_features_has_every_column(small_ds):
    snap = make_snapshot(small_ds, small_ds.last_week)
    user = snap.history["customer_idx"].iloc[0]
    cands = snap.history[snap.history["customer_idx"] == user][["customer_idx", "article_id"]].drop_duplicates()
    for c in ["src_pop", "src_rep", "src_cooc", "src_tt", "rank_pop", "rank_rep", "rank_cooc", "rank_tt",
              "cooc_score", "tt_score", "content_sim"]:
        cands[c] = 0.0
    df = build_features(cands, snap)
    assert set(FEATURES) <= set(df.columns)
    assert (df["ui_bought_count"] >= 1).all()  # every candidate here came from the user's history
