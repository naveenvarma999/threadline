"""Two-tower: the NumPy serving path must reproduce the PyTorch training path."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from threadline.features import age_band  # noqa: E402
from threadline.two_tower import TwoTowerNumpy, train_two_tower  # noqa: E402


@pytest.fixture(scope="module")
def trained(small_ds, random_content):
    tx = small_ds.transactions[small_ds.transactions["week"] < small_ds.last_week]
    return train_two_tower(tx, small_ds.articles, small_ds.customers, random_content, dim=16, epochs=1,
                           batch_size=256, return_torch=True)


def test_numpy_matches_torch(trained):
    exported, item_tower, user_tower = trained
    hist_rows = [[0, 5, 9], [], [3]]
    ages = np.array([22.0, 40.0, 61.0])
    online = np.array([0.2, 0.5, 1.0], dtype=np.float32)
    np_vecs = exported.encode_users(hist_rows, age_band(ages), online)

    L = 3
    hist = torch.zeros((3, L), dtype=torch.long)
    for i, rows in enumerate(hist_rows):
        if rows:
            hist[i, -len(rows):] = torch.tensor(rows) + 1  # torch side uses 1-based ids (0 = padding)
    with torch.no_grad():
        hv = item_tower(hist)
        t_vecs = user_tower(hv, (hist > 0).float(), torch.tensor(age_band(ages), dtype=torch.long),
                            torch.tensor(online)).numpy()
    np.testing.assert_allclose(np_vecs, t_vecs, atol=1e-5)


def test_vectors_are_normalised_and_roundtrip(trained, tmp_path):
    exported, _, _ = trained
    np.testing.assert_allclose(np.linalg.norm(exported.item_vecs, axis=1), 1.0, atol=1e-4)
    exported.save(tmp_path / "tt.npz")
    loaded = TwoTowerNumpy.load(tmp_path / "tt.npz")
    np.testing.assert_array_equal(loaded.item_vecs, exported.item_vecs)


def test_retrieval_beats_random(small_ds, trained):
    """Items a user buys next should rank higher than random items on average."""
    exported, _, _ = trained
    row_of = pd.Series(np.arange(len(small_ds.articles)), index=small_ds.articles["article_id"])
    tx = small_ds.transactions
    last = tx[tx["week"] == small_ds.last_week]
    past = tx[tx["week"] < small_ds.last_week].sort_values("t_dat", ascending=False)
    users = last["customer_idx"].unique()[:200]
    hist = [row_of.reindex(past.loc[past["customer_idx"] == u, "article_id"].head(20)).dropna().astype(int).tolist()
            for u in users]
    ages = small_ds.customers.set_index("customer_idx").loc[users, "age"].to_numpy()
    u = exported.encode_users(hist, age_band(ages), np.full(len(users), 0.5))
    scores = u @ exported.item_vecs.T
    pos_rank = []
    for i, uid in enumerate(users):
        rows = row_of.reindex(last.loc[last["customer_idx"] == uid, "article_id"]).dropna().astype(int)
        ranks = (-scores[i]).argsort().argsort()
        pos_rank.extend(ranks[rows] / len(exported.item_vecs))
    assert np.mean(pos_rank) < 0.45  # random would be ~0.5
