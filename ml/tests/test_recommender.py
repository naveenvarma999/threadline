"""Candidate generation + online recommender on a bundle built without TensorFlow."""

import numpy as np
import pytest

pytest.importorskip("torch")

from threadline.bundle import Recommender, save_bundle  # noqa: E402
from threadline.features import build_features, make_snapshot  # noqa: E402
from threadline.ranker import train_ranker  # noqa: E402
from threadline.retrieval import CandidateGenerator, RetrievalModels, build_cooccurrence  # noqa: E402
from threadline.two_tower import train_two_tower  # noqa: E402


@pytest.fixture(scope="module")
def bundle(small_ds, random_content, tmp_path_factory):
    ds = small_ds
    T = ds.last_week
    tx = ds.transactions[ds.transactions["week"] < T - 1]
    tt = train_two_tower(tx, ds.articles, ds.customers, random_content, dim=16, epochs=1, batch_size=256)
    retr = RetrievalModels(tt, random_content, build_cooccurrence(tx), ds.articles["article_id"].to_numpy())
    gen = CandidateGenerator(retr, ds.customers.set_index("customer_idx")["age"])
    snap = make_snapshot(ds, T - 1)
    buyers = ds.transactions.loc[ds.transactions["week"] == T - 1, "customer_idx"].unique()
    feats = build_features(gen.generate(buyers, snap), snap)
    bought = set(zip(*ds.transactions.loc[ds.transactions["week"] == T - 1, ["customer_idx", "article_id"]].T.values))
    feats["label"] = [int(p in bought) for p in zip(feats["customer_idx"], feats["article_id"])]
    model = train_ranker(feats, max_iter=50)
    out = tmp_path_factory.mktemp("bundle")
    save_bundle(out, articles=ds.articles, customers=ds.customers, snapshot=make_snapshot(ds, T + 1),
                retrieval=retr, ranker=model, metadata={"model_name": "test", "metrics": {}})
    return Recommender(out), gen, snap, feats


def test_candidates_have_all_sources(bundle):
    _, _, _, feats = bundle
    for s in ("pop", "rep", "cooc", "tt"):
        assert feats[f"src_{s}"].sum() > 0, s
    assert not feats.duplicated(["customer_idx", "article_id"]).any()


def test_recommend_known_customer(bundle, small_ds):
    rec = bundle[0]
    idx = bundle[3]["customer_idx"].iloc[0]
    cid = small_ds.customers.loc[small_ds.customers["customer_idx"] == idx, "customer_id"].iloc[0]
    out = rec.recommend(cid, k=12)
    assert len(out) == 12
    assert len({r.article_id for r in out}) == 12
    assert all(r.reason for r in out)
    scores = [r.score for r in out]
    assert scores == sorted(scores, reverse=True)


def test_cold_start_uses_session_items(bundle, small_ds):
    rec = bundle[0]
    cold = rec.recommend(None, k=12, age=25)
    assert len(cold) == 12
    item = int(small_ds.articles["article_id"].iloc[0])
    warm = rec.recommend(None, k=12, recent_article_ids=[item], age=25)
    assert [r.article_id for r in cold] != [r.article_id for r in warm]


def test_exclude_and_similar(bundle, small_ds):
    rec = bundle[0]
    first = rec.recommend(None, k=5, age=30)
    again = rec.recommend(None, k=5, age=30, exclude=[first[0].article_id])
    assert first[0].article_id not in {r.article_id for r in again}
    item = int(small_ds.articles["article_id"].iloc[3])
    sim = rec.similar(item, k=8)
    assert len(sim) == 8 and item not in {a for a, _ in sim}
    assert np.all(np.diff([s for _, s in sim]) <= 1e-9)
