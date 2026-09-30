"""Point-in-time feature snapshots and the ranker feature builder.

The same ``Snapshot`` + ``build_features`` code runs offline (building training data for many
users) and online (scoring one user's candidates inside the inference service). Sharing the
code is how the project avoids training/serving skew.

Leakage rule: a snapshot for reference week ``t`` only sees transactions with ``week < t``.
``tests/test_leakage.py`` enforces this.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from threadline.data import Dataset

HISTORY_LEN = 50
AGE_BINS = [0, 25, 35, 45, 55, 200]
ATTRS = ["product_type_name", "department_name", "colour_group_name", "index_group_name"]


def age_band(age: np.ndarray | pd.Series) -> np.ndarray:
    return np.digitize(np.asarray(age, dtype=float), AGE_BINS[1:-1]).astype(np.int8)


def week_start(ds: Dataset, week: int) -> pd.Timestamp:
    """First calendar day of ``week`` (weeks end on the dataset's last day)."""
    last_day = ds.transactions["t_dat"].max().normalize()
    return last_day - pd.Timedelta(days=7 * (ds.last_week - week) + 6)


@dataclass
class Snapshot:
    ref_week: int
    ref_date: pd.Timestamp
    history: pd.DataFrame  # customer_idx, article_id, t_dat (most recent HISTORY_LEN per user)
    user_feats: pd.DataFrame  # index: customer_idx
    item_feats: pd.DataFrame  # index: article_id
    articles: pd.DataFrame  # index: article_id, ATTRS
    popular: dict[int, list[int]] = field(default_factory=dict)  # age band -> article ids
    popular_global: list[int] = field(default_factory=list)

    # ---- persistence (used by the model bundle)
    def save(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)
        self.history.to_parquet(d / "history.parquet", index=False)
        self.user_feats.to_parquet(d / "user_feats.parquet")
        self.item_feats.to_parquet(d / "item_feats.parquet")
        meta = {
            "ref_week": self.ref_week,
            "ref_date": self.ref_date.isoformat(),
            "popular": {str(k): v for k, v in self.popular.items()},
            "popular_global": self.popular_global,
        }
        (d / "snapshot.json").write_text(json.dumps(meta))

    @classmethod
    def load(cls, d: Path, articles: pd.DataFrame) -> Snapshot:
        meta = json.loads((d / "snapshot.json").read_text())
        return cls(
            ref_week=meta["ref_week"],
            ref_date=pd.Timestamp(meta["ref_date"]),
            history=pd.read_parquet(d / "history.parquet"),
            user_feats=pd.read_parquet(d / "user_feats.parquet"),
            item_feats=pd.read_parquet(d / "item_feats.parquet"),
            articles=_article_attrs(articles),
            popular={int(k): v for k, v in meta["popular"].items()},
            popular_global=meta["popular_global"],
        )


def _article_attrs(articles: pd.DataFrame) -> pd.DataFrame:
    a = articles.set_index("article_id")[ATTRS].copy()
    for c in ATTRS:
        a[c] = a[c].astype(str)
    return a


def make_snapshot(ds: Dataset, ref_week: int, n_popular: int = 30) -> Snapshot:
    """Build all point-in-time tables for scoring week ``ref_week``."""
    tx = ds.transactions
    past = tx[tx["week"] < ref_week]
    if past.empty:
        raise ValueError(f"No history before week {ref_week}")
    ref_date = week_start(ds, ref_week) if ref_week <= ds.last_week else (
        tx["t_dat"].max().normalize() + pd.Timedelta(days=1)
    )
    articles = _article_attrs(ds.articles)

    # ---- per-user history (most recent first)
    hist = past.sort_values("t_dat", ascending=False)
    hist = hist.groupby("customer_idx", sort=False).head(HISTORY_LEN)
    history = hist[["customer_idx", "article_id", "t_dat", "price"]].reset_index(drop=True)

    # ---- user features
    days_ago = (ref_date - past["t_dat"]).dt.days
    past = past.assign(
        days_ago=days_ago,
        online=(past["sales_channel_id"] == 2).astype(np.float32),
        in_1w=(days_ago < 7).astype(np.int32),
        in_2w=(days_ago < 14).astype(np.int32),
        in_4w=(days_ago < 28).astype(np.int32),
    )
    g = past.groupby("customer_idx")
    uf = pd.DataFrame({
        "u_n_all": g.size(),
        "u_n_1w": g["in_1w"].sum(),
        "u_n_4w": g["in_4w"].sum(),
        "u_days_since_last": g["days_ago"].min(),
        "u_mean_price": g["price"].mean(),
        "u_std_price": g["price"].std().fillna(0),
        "u_online_ratio": g["online"].mean(),
        "u_n_unique": g["article_id"].nunique(),
    })
    cust = ds.customers.set_index("customer_idx")
    uf = uf.join(cust[["age"]], how="left")
    uf["u_age"] = uf.pop("age").fillna(cust["age"].median())
    uf = uf.astype(np.float32)

    # ---- item features
    ig = past.groupby("article_id")
    itf = pd.DataFrame({
        "i_sales_1w": ig["in_1w"].sum(),
        "i_sales_2w": ig["in_2w"].sum(),
        "i_sales_4w": ig["in_4w"].sum(),
        "i_sales_all": ig.size(),
        "i_days_since_first": ig["days_ago"].max(),
        "i_days_since_last": ig["days_ago"].min(),
        "i_mean_price": ig["price"].mean(),
        "i_n_buyers": ig["customer_idx"].nunique(),
    })
    itf["i_trend"] = itf["i_sales_1w"] / (itf["i_sales_4w"] / 4 + 1)
    itf["i_repurchase_rate"] = 1 - itf["i_n_buyers"] / itf["i_sales_all"]
    ptype = articles["product_type_name"].reindex(itf.index)
    itf["i_price_rel_type"] = itf["i_mean_price"] / itf.groupby(ptype.to_numpy())["i_mean_price"].transform("median")
    itf = itf.astype(np.float32)

    # ---- popularity lists (last 7 days), overall and per age band
    recent = past[days_ago < 7]
    if recent.empty:
        recent = past[days_ago < 28]
    popular_global = recent["article_id"].value_counts().head(n_popular).index.astype(int).tolist()
    bands = pd.Series(age_band(cust["age"].reindex(recent["customer_idx"]).to_numpy()), index=recent.index)
    popular = {
        int(b): grp["article_id"].value_counts().head(n_popular).index.astype(int).tolist()
        for b, grp in recent.groupby(bands)
    }
    return Snapshot(ref_week, ref_date, history, uf, itf, articles, popular, popular_global)


# --------------------------------------------------------------------------------------
# Feature builder
# --------------------------------------------------------------------------------------

USER_COLS = ["u_n_all", "u_n_1w", "u_n_4w", "u_days_since_last", "u_mean_price", "u_std_price",
             "u_online_ratio", "u_n_unique", "u_age"]
ITEM_COLS = ["i_sales_1w", "i_sales_2w", "i_sales_4w", "i_sales_all", "i_days_since_first",
             "i_days_since_last", "i_mean_price", "i_n_buyers", "i_trend", "i_repurchase_rate",
             "i_price_rel_type"]
CAND_COLS = ["src_pop", "src_rep", "src_cooc", "src_tt", "rank_pop", "rank_rep", "rank_cooc", "rank_tt",
             "cooc_score", "tt_score", "content_sim"]
UI_COLS = ["ui_bought_count", "ui_days_since_bought", "ui_type_share", "ui_dept_share", "ui_colour_share",
           "ui_index_share", "ui_price_ratio"]
FEATURES = USER_COLS + ITEM_COLS + CAND_COLS + UI_COLS


def build_features(cands: pd.DataFrame, snap: Snapshot, history: pd.DataFrame | None = None) -> pd.DataFrame:
    """Join user, item and user-x-item features onto a candidate table.

    ``cands`` needs ``customer_idx``, ``article_id`` and the ``CAND_COLS`` produced by the
    candidate generator. ``history`` overrides ``snap.history`` (used online to add items from
    the current session).
    """
    history = snap.history if history is None else history
    df = cands.join(snap.user_feats, on="customer_idx")
    df = df.join(snap.item_feats, on="article_id")

    # user x item: repeat purchases of the same article
    h = history[history["customer_idx"].isin(df["customer_idx"].unique())]
    days = (snap.ref_date - h["t_dat"]).dt.days
    ui = h.assign(days=days).groupby(["customer_idx", "article_id"]).agg(
        ui_bought_count=("days", "size"), ui_days_since_bought=("days", "min"))
    df = df.join(ui, on=["customer_idx", "article_id"])

    # user x attribute shares: how much of the user's history is in the candidate's type/dept/...
    ha = h[["customer_idx", "article_id", "price"]].join(snap.articles, on="article_id")
    n_hist = ha.groupby("customer_idx").size().rename("n")
    cand_attr = df[["customer_idx", "article_id"]].join(snap.articles, on="article_id")
    for attr, col in zip(ATTRS, ["ui_type_share", "ui_dept_share", "ui_colour_share", "ui_index_share"]):
        counts = ha.groupby(["customer_idx", attr]).size().rename("c")
        joined = cand_attr[["customer_idx", attr]].join(counts, on=["customer_idx", attr])["c"].fillna(0)
        df[col] = (joined / cand_attr["customer_idx"].map(n_hist).fillna(1)).to_numpy()
    user_price = ha.groupby("customer_idx")["price"].mean()
    df["ui_price_ratio"] = df["i_mean_price"] / df["customer_idx"].map(user_price)

    df["ui_bought_count"] = df["ui_bought_count"].fillna(0)
    df["ui_days_since_bought"] = df["ui_days_since_bought"].fillna(999)
    for c in FEATURES:
        if c not in df:
            df[c] = np.nan
    df[FEATURES] = df[FEATURES].astype(np.float32)
    return df
