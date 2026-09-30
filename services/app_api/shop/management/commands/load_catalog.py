"""Seed the shop database from the ML pipeline's processed Parquet files.

    python manage.py load_catalog --processed-dir ../../data/processed --customers 2000

Loads every article, the most active customers, and their purchases from the last 8 weeks.
"""

from __future__ import annotations

from datetime import timezone as dt_tz
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import Article, Customer, Purchase

# H&M prices are normalised. Multiplying by this factor gives plausible GBP display prices.
PRICE_SCALE = 590


def _gbp(x: float) -> Decimal:
    return Decimal(str(round(max(float(x) * PRICE_SCALE, 1.0), 2)))


class Command(BaseCommand):
    help = "Load articles, customers and recent purchases from processed Parquet files"

    def add_arguments(self, parser):
        parser.add_argument("--processed-dir", default="../../data/processed")
        parser.add_argument("--customers", type=int, default=2000)
        parser.add_argument("--weeks", type=int, default=8)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **o):
        d = Path(o["processed_dir"])
        arts = pd.read_parquet(d / "articles.parquet")
        custs = pd.read_parquet(d / "customers.parquet")
        tx = pd.read_parquet(d / "transactions.parquet")
        tx = tx[tx["week"] > tx["week"].max() - o["weeks"]]
        last4 = tx[tx["week"] > tx["week"].max() - 4]
        sales = last4["article_id"].value_counts()
        mean_price = tx.groupby("article_id")["price"].mean()
        overall = mean_price.median()

        with transaction.atomic():
            if o["reset"]:
                Purchase.objects.all().delete()
                Customer.objects.all().delete()
                Article.objects.all().delete()
            Article.objects.bulk_create([
                Article(article_id=int(r.article_id), prod_name=r.prod_name, product_type=r.product_type_name,
                        product_group=r.product_group_name, colour=r.colour_group_name,
                        department=r.department_name, index_group=r.index_group_name,
                        garment_group=r.garment_group_name, description=r.detail_desc,
                        price=_gbp(mean_price.get(r.article_id, overall)),
                        sales_last_4w=int(sales.get(r.article_id, 0)))
                for r in arts.itertuples(index=False)
            ], batch_size=2000, ignore_conflicts=True)

            active = tx["customer_idx"].value_counts().head(o["customers"])
            chosen = custs[custs["customer_idx"].isin(active.index)]
            Customer.objects.bulk_create([
                Customer(customer_id=r.customer_id, age=int(r.age) if pd.notna(r.age) else None,
                         club_member_status=r.club_member_status or "",
                         fashion_news_frequency=r.fashion_news_frequency or "",
                         n_purchases=int(active.get(r.customer_idx, 0)))
                for r in chosen.itertuples(index=False)
            ], batch_size=2000, ignore_conflicts=True)

            id_of = dict(zip(chosen["customer_idx"], chosen["customer_id"]))
            ptx = tx[tx["customer_idx"].isin(id_of)]
            Purchase.objects.bulk_create([
                Purchase(customer_id=id_of[r.customer_idx], article_id=int(r.article_id),
                         purchased_at=pd.Timestamp(r.t_dat).to_pydatetime().replace(tzinfo=dt_tz.utc),
                         price=_gbp(r.price), channel=int(r.sales_channel_id))
                for r in ptx.itertuples(index=False)
            ], batch_size=5000)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(arts)} articles, {len(chosen)} customers, {len(ptx)} purchases"))
