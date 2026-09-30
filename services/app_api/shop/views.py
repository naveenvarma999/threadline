from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from shop import inference
from shop.inference import InferenceUnavailable
from shop.models import Article, Customer, Event, Purchase
from shop.serializers import (
    ArticleSerializer,
    CheckoutSerializer,
    CustomerSerializer,
    EventSerializer,
    FeedRequestSerializer,
)

log = logging.getLogger(__name__)


def hydrate(items: list[dict], extra_keys=("score", "reason", "sources")) -> list[dict]:
    """Turn [{article_id, score, ...}] into full article payloads, keeping order."""
    ids = [i["article_id"] for i in items]
    by_id = {a.article_id: a for a in Article.objects.filter(article_id__in=ids)}
    out = []
    for i in items:
        a = by_id.get(i["article_id"])
        if a is None:
            continue
        row = ArticleSerializer(a).data
        for k in extra_keys:
            if k in i:
                row[k] = i[k]
        out.append(row)
    return out


def db_trending(k: int, exclude: set[int] = frozenset()) -> list[dict]:
    qs = Article.objects.exclude(article_id__in=exclude).order_by("-sales_last_4w")[:k]
    return [ArticleSerializer(a).data | {"reason": "Popular right now", "sources": ["pop"]} for a in qs]


# ---------------------------------------------------------------------------- catalogue
@api_view(["GET"])
def health(_request):
    return Response({"status": "ok", "articles": Article.objects.count()})


class ArticleList(generics.ListAPIView):
    serializer_class = ArticleSerializer

    def get_queryset(self):
        qs = Article.objects.all()
        p = self.request.query_params
        if q := p.get("q"):
            qs = qs.filter(Q(prod_name__icontains=q) | Q(product_type__icontains=q) | Q(colour__icontains=q))
        for field in ("product_group", "index_group", "colour", "product_type"):
            if v := p.get(field):
                qs = qs.filter(**{field: v})
        return qs


@api_view(["GET"])
def facets(_request):
    return Response({f: list(Article.objects.values_list(f, flat=True).distinct().order_by(f))
                     for f in ("product_group", "index_group", "colour")})


class ArticleDetail(generics.RetrieveAPIView):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer


@api_view(["GET"])
def article_similar(_request, pk: int):
    a = get_object_or_404(Article, pk=pk)
    try:
        items = hydrate([i | {"reason": "Similar style"} for i in inference.similar(pk, 12)])
    except InferenceUnavailable:
        items = [ArticleSerializer(x).data for x in
                 Article.objects.filter(product_type=a.product_type).exclude(pk=pk)[:12]]
    return Response(items)


@api_view(["GET"])
def article_complete_the_look(_request, pk: int):
    get_object_or_404(Article, pk=pk)
    try:
        items = hydrate([i | {"reason": "Often bought together"} for i in inference.bought_together(pk, 6)])
    except InferenceUnavailable:
        items = []
    return Response(items)


# ---------------------------------------------------------------------------- customers + feed
@api_view(["GET"])
def demo_customers(request):
    """Customers with rich histories, for the storefront's "shop as" picker."""
    n = min(int(request.query_params.get("n", 12)), 50)
    qs = Customer.objects.filter(n_purchases__gte=3).order_by("-n_purchases")[:n]
    return Response(CustomerSerializer(qs, many=True).data)


@api_view(["GET"])
def customer_detail(_request, pk: str):
    c = get_object_or_404(Customer, pk=pk)
    recent = c.purchases.select_related("article")[:12]
    return Response(CustomerSerializer(c).data | {
        "recent_purchases": [ArticleSerializer(p.article).data | {"purchased_at": p.purchased_at} for p in recent]
    })


@api_view(["POST"])
def feed(request):
    s = FeedRequestSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    cid = s.validated_data.get("customer_id") or None
    session = s.validated_data.get("session_article_ids", [])
    age = s.validated_data.get("age")
    customer = Customer.objects.filter(pk=cid).first() if cid else None
    if customer and customer.age:
        age = customer.age
    try:
        rec = inference.recommend(cid, k=30, recent=session, age=age, exclude=[])
        items = rec["items"]
        buy_again = [i for i in items if "rep" in i["sources"]][:8]
        for_you = [i for i in items if "rep" not in i["sources"]][:12]
        shown = {i["article_id"] for i in for_you + buy_again}
        trending_ids = [a for a in inference.popular(24, age) if a not in shown][:12]
        trending = [{"article_id": a, "reason": "Trending with shoppers like you", "sources": ["pop"]}
                    for a in trending_ids]
        body = {
            "model_version": rec["model_version"], "fallback": rec["fallback"],
            "rows": [
                {"key": "for_you", "title": "Picked for you", "items": hydrate(for_you)},
                {"key": "buy_again", "title": "Buy again", "items": hydrate(buy_again)},
                {"key": "trending", "title": "Trending this week", "items": hydrate(trending)},
            ],
        }
    except InferenceUnavailable:
        body = {"model_version": "unavailable", "fallback": True,
                "rows": [{"key": "trending", "title": "Popular right now", "items": db_trending(24)}]}
    body["rows"] = [r for r in body["rows"] if r["items"]]
    return Response(body)


# ---------------------------------------------------------------------------- events + checkout
@api_view(["POST"])
def events(request):
    many = isinstance(request.data, list)
    s = EventSerializer(data=request.data, many=many)
    s.is_valid(raise_exception=True)
    s.save()
    return Response({"created": len(request.data) if many else 1}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def checkout(request):
    s = CheckoutSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    customer = Customer.objects.filter(pk=d.get("customer_id")).first() if d.get("customer_id") else None
    articles = list(Article.objects.filter(article_id__in=d["article_ids"]))
    now = timezone.now()
    with transaction.atomic():
        Event.objects.bulk_create([Event(session_id=d["session_id"], customer=customer, article=a,
                                         event_type=Event.Type.PURCHASE, placement="checkout") for a in articles])
        if customer:
            Purchase.objects.bulk_create([Purchase(customer=customer, article=a, purchased_at=now, price=a.price)
                                          for a in articles])
            Customer.objects.filter(pk=customer.pk).update(n_purchases=customer.n_purchases + len(articles))
    total = sum((a.price for a in articles), Decimal("0"))
    return Response({"order_items": len(articles), "total": str(total)}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------- ops console
class HasOpsToken(BasePermission):
    message = "Missing or invalid X-Ops-Token header."

    def has_permission(self, request, view):
        return request.headers.get("X-Ops-Token") == settings.OPS_TOKEN


def _engagement() -> list[dict]:
    rows = (Event.objects.values("placement")
            .annotate(impressions=Count("id", filter=Q(event_type="impression")),
                      clicks=Count("id", filter=Q(event_type="click")),
                      add_to_cart=Count("id", filter=Q(event_type="add_to_cart")))
            .order_by("placement"))
    out = []
    for r in rows:
        if not r["placement"] or r["placement"] == "checkout":
            continue
        imp = r["impressions"]
        out.append(r | {"ctr": r["clicks"] / imp if imp else None,
                        "add_to_cart_rate": r["add_to_cart"] / imp if imp else None})
    return out


@api_view(["GET"])
@permission_classes([HasOpsToken])
def ops_overview(_request):
    body = {"engagement": _engagement(),
            "events_24h": dict(Event.objects.filter(created_at__gte=timezone.now() - timezone.timedelta(days=1))
                               .values_list("event_type").annotate(n=Count("id")))}
    try:
        body["model"] = inference.model_info()
        body["service"] = inference.stats()
        body["inference_status"] = "ok"
    except InferenceUnavailable as e:
        body["inference_status"] = f"unavailable: {e}"
    return Response(body)


@api_view(["GET"])
@permission_classes([HasOpsToken])
def ops_models(_request):
    if not settings.MLFLOW_TRACKING_URI:
        return Response({"registry": "not configured", "versions": []})
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    c = MlflowClient()
    versions = []
    for found in c.search_model_versions(f"name='{settings.REGISTERED_MODEL}'"):
        mv = c.get_model_version(settings.REGISTERED_MODEL, found.version)  # search results omit aliases
        run = c.get_run(mv.run_id)
        versions.append({
            "version": mv.version, "aliases": list(mv.aliases), "created": mv.creation_timestamp,
            "run_id": mv.run_id, "data_source": run.data.params.get("data_source"),
            "metrics": {k: v for k, v in run.data.metrics.items() if k.startswith("test_")},
        })
    versions.sort(key=lambda v: int(v["version"]), reverse=True)
    return Response({"registry": settings.REGISTERED_MODEL, "versions": versions})


@api_view(["POST"])
@permission_classes([HasOpsToken])
def ops_promote(_request, version: str):
    if not settings.MLFLOW_TRACKING_URI:
        return Response({"detail": "MLflow registry is not configured"}, status=400)
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    MlflowClient().set_registered_model_alias(settings.REGISTERED_MODEL, "champion", version)
    log.info("Promoted version %s to champion via ops console", version)
    try:
        reload = inference.reload_model()
    except InferenceUnavailable as e:
        reload = {"error": str(e)}
    return Response({"champion": version, "inference_reload": reload})
