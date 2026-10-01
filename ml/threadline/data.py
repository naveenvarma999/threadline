"""Data loading.

Two sources share one schema (the H&M Kaggle schema):

* Real data: put ``articles.csv``, ``customers.csv`` and ``transactions_train.csv`` from the
  H&M Personalized Fashion Recommendations competition in ``data/raw/hm/``. Read the
  competition rules before using the data; they govern what you may do with it.
* Synthetic data: ``generate_synthetic()`` builds a smaller dataset with the same columns and
  realistic structure (taste, trends, seasonality, repurchase, outfit co-purchase), so the
  whole system runs and can be tested without downloading anything.

``prepare()`` turns either source into compact Parquet files with integer ids and a
``week`` column, where the last week in the data has the highest index.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from threadline.config import Paths, TrainConfig

log = logging.getLogger(__name__)

HM_FILES = ("articles.csv", "customers.csv", "transactions_train.csv")

ARTICLE_COLUMNS = [
    "article_id", "prod_name", "product_type_name", "product_group_name", "colour_group_name",
    "department_name", "index_group_name", "garment_group_name", "detail_desc",
]


@dataclass
class Dataset:
    transactions: pd.DataFrame  # customer_idx, article_id, t_dat, week, price, sales_channel_id
    articles: pd.DataFrame
    customers: pd.DataFrame  # customer_idx, customer_id, age, club_member_status, fashion_news_frequency

    @property
    def last_week(self) -> int:
        return int(self.transactions["week"].max())


# --------------------------------------------------------------------------------------
# Synthetic generator
# --------------------------------------------------------------------------------------

_GROUPS = {
    "Garment Upper body": (["T-shirt", "Sweater", "Blouse", "Shirt", "Hoodie", "Jacket"], 0.35),
    "Garment Lower body": (["Trousers", "Skirt", "Shorts", "Jeans"], 0.22),
    "Garment Full body": (["Dress", "Jumpsuit"], 0.12),
    "Shoes": (["Sneakers", "Boots", "Sandals"], 0.08),
    "Accessories": (["Bag", "Scarf", "Hat", "Belt"], 0.1),
    "Underwear": (["Bra", "Socks", "Briefs"], 0.08),
    "Swimwear": (["Swimsuit", "Bikini top"], 0.05),
}
_COMPLEMENT = {
    "Garment Upper body": ["Garment Lower body", "Accessories"],
    "Garment Lower body": ["Garment Upper body", "Shoes"],
    "Garment Full body": ["Shoes", "Accessories"],
    "Shoes": ["Garment Lower body"],
    "Accessories": ["Garment Upper body"],
    "Underwear": ["Underwear"],
    "Swimwear": ["Swimwear", "Accessories"],
}
_INDEX_GROUPS = ["Ladieswear", "Menswear", "Divided", "Sport", "Baby/Children"]
_COLOURS = ["Black", "White", "Light Beige", "Dark Blue", "Grey", "Pink", "Red", "Khaki green",
            "Light Blue", "Yellow", "Brown", "Off White"]
_FITS = ["Relaxed", "Slim", "Regular", "Oversized", "Fitted", "Cropped"]
_MATERIALS = ["cotton jersey", "soft rib knit", "woven fabric", "denim", "recycled polyester",
              "linen blend", "fine-knit wool blend", "satin"]
_DETAILS = ["with a round neckline", "with side pockets", "with a drawstring waist", "with long sleeves",
            "with a V-neck", "with a zip at the front", "with adjustable straps", "with a high waist"]
_PRICE = {"T-shirt": .012, "Sweater": .03, "Blouse": .025, "Shirt": .028, "Hoodie": .033, "Jacket": .06,
          "Trousers": .035, "Skirt": .025, "Shorts": .02, "Jeans": .04, "Dress": .04, "Jumpsuit": .045,
          "Sneakers": .05, "Boots": .07, "Sandals": .03, "Bag": .03, "Scarf": .015, "Hat": .012,
          "Belt": .012, "Bra": .02, "Socks": .006, "Briefs": .008, "Swimsuit": .03, "Bikini top": .018}
_SEASONAL = {"Swimwear": 1.5, "Garment Full body": 0.4, "Shoes": 0.2}  # summer uplift per group


def generate_synthetic(
    n_articles: int = 2500,
    n_customers: int = 30000,
    n_weeks: int = 20,
    seed: int = 7,
    end_date: str = "2020-09-22",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (articles, customers, transactions) in raw H&M format."""
    rng = np.random.default_rng(seed)
    style_dim = 8

    # ---- articles
    group_names = list(_GROUPS)
    group_p = np.array([_GROUPS[g][1] for g in group_names])
    groups = rng.choice(group_names, size=n_articles, p=group_p / group_p.sum())
    ptypes = np.array([rng.choice(_GROUPS[g][0]) for g in groups])
    index_groups = rng.choice(_INDEX_GROUPS, size=n_articles, p=[.38, .18, .22, .1, .12])
    colours = rng.choice(_COLOURS, size=n_articles)
    index_vec = {g: rng.normal(size=style_dim) for g in _INDEX_GROUPS}
    colour_vec = {c: rng.normal(scale=.6, size=style_dim) for c in _COLOURS}
    style = np.stack([index_vec[i] + colour_vec[c] for i, c in zip(index_groups, colours)])
    style += rng.normal(scale=.5, size=style.shape)
    base_pop = rng.lognormal(mean=0, sigma=1.0, size=n_articles)
    launch = rng.integers(-12, n_weeks - 1, size=n_articles)  # some items launch mid-period
    fits = rng.choice(_FITS, size=n_articles)
    mats = rng.choice(_MATERIALS, size=n_articles)
    dets = rng.choice(_DETAILS, size=n_articles)
    candidate_ids = np.unique(rng.integers(108_000_000, 959_000_000, size=n_articles * 2))
    article_ids = np.sort(rng.permutation(candidate_ids)[:n_articles])
    prod_names = [f"{f} {m.split()[-1].title()} {p}" for f, m, p in zip(fits, mats, ptypes)]
    articles = pd.DataFrame({
        "article_id": article_ids,
        "prod_name": prod_names,
        "product_type_name": ptypes,
        "product_group_name": groups,
        "colour_group_name": colours,
        "department_name": [f"{i} {g.split()[-1].title()}" for i, g in zip(index_groups, groups)],
        "index_group_name": index_groups,
        "garment_group_name": [p if g.startswith("Garment") else g for p, g in zip(ptypes, groups)],
        "detail_desc": [f"{f} {p.lower()} in {c.lower()} {m} {d}." for f, p, c, m, d in
                        zip(fits, ptypes, colours, mats, dets)],
    })
    price = np.array([_PRICE[p] for p in ptypes]) * rng.lognormal(0, .25, size=n_articles)

    # Complementary items ("complete the look") by style similarity inside complement groups.
    norm_style = style / np.linalg.norm(style, axis=1, keepdims=True)
    complements = np.zeros((n_articles, 5), dtype=np.int64)
    for g in group_names:
        src = np.where(groups == g)[0]
        tgt = np.where(np.isin(groups, _COMPLEMENT[g]))[0]
        if len(src) == 0 or len(tgt) == 0:
            continue
        sim = norm_style[src] @ norm_style[tgt].T
        complements[src] = tgt[np.argsort(-sim, axis=1)[:, :5]]

    # ---- customers
    age = np.clip(rng.normal(34, 11, size=n_customers), 16, 80).round()
    fav_index = rng.choice(_INDEX_GROUPS, size=n_customers, p=[.42, .2, .2, .1, .08])
    cust_style = np.stack([index_vec[i] for i in fav_index]) + rng.normal(scale=.8, size=(n_customers, style_dim))
    activity = rng.gamma(shape=0.6, scale=0.35, size=n_customers)  # weekly purchase prob (heavy tail)
    online = rng.random(n_customers) < 0.65
    price_sens = rng.normal(0, 1, size=n_customers)
    customer_ids = [f"{x:016x}" for x in rng.integers(0, 2**63, size=n_customers)]
    customers = pd.DataFrame({
        "customer_id": customer_ids,
        "age": age,
        "club_member_status": rng.choice(["ACTIVE", "PRE-CREATE", "LEFT CLUB"], size=n_customers, p=[.9, .08, .02]),
        "fashion_news_frequency": rng.choice(["NONE", "Regularly", "Monthly"], size=n_customers, p=[.63, .36, .01]),
        "postal_code": [f"{x:08x}" for x in rng.integers(0, 2**31, size=n_customers)],
    })

    # ---- transactions, week by week
    end = pd.Timestamp(end_date)
    start = end - pd.Timedelta(days=7 * n_weeks - 1)
    rows = []
    past: dict[int, list[int]] = {}
    item_log_price = np.log(price)
    for w in range(n_weeks):
        age_w = w - launch
        lifecycle = np.where(age_w < 0, 0.0, np.exp(-((age_w - 3) ** 2) / 40.0) + 0.15)
        season = 1 + np.array([_SEASONAL.get(g, 0.0) for g in groups]) * np.sin(np.pi * w / n_weeks)
        log_pop = np.log(base_pop * lifecycle * season + 1e-9)
        buyers = np.where(rng.random(n_customers) < np.clip(activity, 0, 0.9))[0]
        if len(buyers) == 0:
            continue
        n_items = rng.poisson(1.6, size=len(buyers)) + 1
        scores = (cust_style[buyers] @ style.T) * 0.55 + log_pop[None, :]
        scores -= 0.6 * price_sens[buyers, None] * item_log_price[None, :]
        scores += rng.gumbel(size=scores.shape)
        top = np.argsort(-scores, axis=1)[:, :8]
        week_days = rng.integers(0, 7, size=len(buyers))
        for bi, c in enumerate(buyers):
            chosen = list(top[bi, : n_items[bi]])
            hist = past.get(c)
            if hist and rng.random() < 0.35:  # repurchase of a basic
                chosen[0] = hist[rng.integers(len(hist))]
            if rng.random() < 0.4:  # outfit completion
                comp = complements[chosen[0]]
                chosen.append(comp[rng.integers(len(comp))])
            day = start + pd.Timedelta(days=7 * w + int(week_days[bi]))
            channel = 2 if online[c] else 1
            for a in chosen:
                if lifecycle[a] == 0:
                    continue
                rows.append((day, c, a, channel))
            past.setdefault(c, []).extend(chosen)

    tx = pd.DataFrame(rows, columns=["t_dat", "cust", "art", "sales_channel_id"])
    tx["customer_id"] = np.array(customer_ids)[tx["cust"].to_numpy()]
    tx["article_id"] = article_ids[tx["art"].to_numpy()]
    tx["price"] = (price[tx["art"].to_numpy()] * rng.uniform(.85, 1.0, size=len(tx))).round(6)
    tx = tx[["t_dat", "customer_id", "article_id", "price", "sales_channel_id"]]
    return articles, customers, tx


# --------------------------------------------------------------------------------------
# Loading and preparation
# --------------------------------------------------------------------------------------

def has_real_hm(paths: Paths) -> bool:
    return all((paths.raw_hm / f).exists() for f in HM_FILES)


def load_raw_hm(paths: Paths, history_weeks: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the H&M CSVs, keeping only the trailing ``history_weeks`` of transactions and the
    customers and articles that appear in them (the full file is ~31M rows)."""
    d = paths.raw_hm
    log.info("Reading real H&M data from %s", d)
    tx = pd.read_csv(
        d / "transactions_train.csv",
        engine="pyarrow",
        dtype={"article_id": np.int64, "price": np.float32, "sales_channel_id": np.int8},
        parse_dates=["t_dat"],
    )
    if history_weeks:
        start = tx["t_dat"].max() - pd.Timedelta(days=7 * history_weeks - 1)
        tx = tx[tx["t_dat"] >= start].reset_index(drop=True)
    log.info("Kept %d transactions from %s to %s", len(tx), tx["t_dat"].min().date(), tx["t_dat"].max().date())
    customers = pd.read_csv(
        d / "customers.csv",
        engine="pyarrow",
        usecols=["customer_id", "age", "club_member_status", "fashion_news_frequency", "postal_code"],
    )
    customers = customers[customers["customer_id"].isin(tx["customer_id"].unique())]
    articles = pd.read_csv(d / "articles.csv", dtype={"article_id": np.int64}, usecols=ARTICLE_COLUMNS)
    articles = articles[articles["article_id"].isin(tx["article_id"].unique())]
    return articles, customers, tx


def prepare(
    articles: pd.DataFrame, customers: pd.DataFrame, tx: pd.DataFrame, cfg: TrainConfig
) -> Dataset:
    """Filter to the trailing window, index ids as compact ints and add a ``week`` column."""
    tx = tx.copy()
    tx["t_dat"] = pd.to_datetime(tx["t_dat"])
    last_day = tx["t_dat"].max()
    weeks_ago = ((last_day - tx["t_dat"]).dt.days // 7).astype(np.int16)
    tx = tx[weeks_ago < cfg.history_weeks].copy()
    weeks_ago = weeks_ago[tx.index]
    tx["week"] = (cfg.history_weeks - 1 - weeks_ago).astype(np.int16)

    if cfg.max_customers:
        active = tx["customer_id"].unique()
        if len(active) > cfg.max_customers:
            rng = np.random.default_rng(cfg.seed)
            keep = set(rng.choice(active, size=cfg.max_customers, replace=False))
            tx = tx[tx["customer_id"].isin(keep)]
            customers = customers[customers["customer_id"].isin(keep)]
            articles = articles[articles["article_id"].isin(tx["article_id"].unique())]
            log.info("Sampled %d of %d active customers", cfg.max_customers, len(active))

    customers = customers.copy()
    customers["age"] = customers["age"].fillna(customers["age"].median()).astype(np.float32)
    for col in ("club_member_status", "fashion_news_frequency"):
        customers[col] = customers[col].fillna("NONE").replace({"None": "NONE"})
    customers = customers.reset_index(drop=True)
    customers["customer_idx"] = np.arange(len(customers), dtype=np.int32)
    cmap = pd.Series(customers["customer_idx"].to_numpy(), index=customers["customer_id"].to_numpy())
    tx["customer_idx"] = cmap.reindex(tx["customer_id"].to_numpy()).to_numpy()
    tx = tx.dropna(subset=["customer_idx"])
    tx["customer_idx"] = tx["customer_idx"].astype(np.int32)

    articles = articles[ARTICLE_COLUMNS].copy()
    articles["article_id"] = articles["article_id"].astype(np.int32)
    articles["detail_desc"] = articles["detail_desc"].fillna("")
    for col in ARTICLE_COLUMNS[2:8]:
        articles[col] = articles[col].astype("category")

    tx = tx[["customer_idx", "article_id", "t_dat", "week", "price", "sales_channel_id"]]
    tx["article_id"] = tx["article_id"].astype(np.int32)
    tx["price"] = tx["price"].astype(np.float32)
    tx["sales_channel_id"] = tx["sales_channel_id"].astype(np.int8)
    tx = tx.sort_values(["t_dat", "customer_idx"]).reset_index(drop=True)
    return Dataset(transactions=tx, articles=articles.reset_index(drop=True), customers=customers)


def save(ds: Dataset, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ds.transactions.to_parquet(out_dir / "transactions.parquet", index=False)
    ds.articles.to_parquet(out_dir / "articles.parquet", index=False)
    ds.customers.to_parquet(out_dir / "customers.parquet", index=False)


def load_processed(out_dir: Path) -> Dataset:
    return Dataset(
        transactions=pd.read_parquet(out_dir / "transactions.parquet"),
        articles=pd.read_parquet(out_dir / "articles.parquet"),
        customers=pd.read_parquet(out_dir / "customers.parquet"),
    )


def build_dataset(paths: Paths, cfg: TrainConfig, source: str = "auto") -> tuple[Dataset, str]:
    """Load real H&M data when present (or when ``source='hm'``), otherwise synthetic."""
    if source == "hm" or (source == "auto" and has_real_hm(paths)):
        raw, name = load_raw_hm(paths, cfg.history_weeks), "hm"
    else:
        log.info("Real H&M files not found in %s; generating synthetic data", paths.raw_hm)
        raw, name = generate_synthetic(n_weeks=max(cfg.history_weeks, 8), seed=cfg.seed), "synthetic"
    ds = prepare(*raw, cfg=cfg)
    save(ds, paths.processed)
    log.info("Prepared %s: %d transactions, %d articles, %d customers",
             name, len(ds.transactions), len(ds.articles), len(ds.customers))
    return ds, name
