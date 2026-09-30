import numpy as np
import pandas as pd
import pytest
from threadline.config import TrainConfig
from threadline.data import generate_synthetic, prepare


@pytest.fixture(scope="session")
def small_ds():
    raw = generate_synthetic(n_articles=400, n_customers=1500, n_weeks=10, seed=3)
    cfg = TrainConfig()
    object.__setattr__(cfg, "history_weeks", 10)
    return prepare(*raw, cfg=cfg)


@pytest.fixture(scope="session")
def random_content(small_ds):
    rng = np.random.default_rng(0)
    e = rng.normal(size=(len(small_ds.articles), 16)).astype(np.float32)
    return e / np.linalg.norm(e, axis=1, keepdims=True)


@pytest.fixture
def tiny_history():
    return pd.DataFrame(
        {"customer_idx": [1], "article_id": [10], "t_dat": [pd.Timestamp("2020-01-01")], "price": [0.02]}
    )
