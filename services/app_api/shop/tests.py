from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from shop.inference import InferenceUnavailable
from shop.models import Article, Customer, Event, Purchase


def make_article(i, **kw):
    defaults = dict(prod_name=f"Item {i}", product_type="T-shirt", product_group="Garment Upper body",
                    colour="Black", department="Ladieswear Body", index_group="Ladieswear",
                    garment_group="T-shirt", description="", price="9.99", sales_last_4w=100 - i)
    return Article.objects.create(article_id=i, **(defaults | kw))


@override_settings(OPS_TOKEN="t0k")
class ApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        for i in range(1, 31):
            make_article(i)
        self.cust = Customer.objects.create(customer_id="abc", age=30, n_purchases=5)
        Purchase.objects.create(customer=self.cust, article_id=1, purchased_at=timezone.now(), price="9.99")

    def test_catalogue_filters_and_detail(self):
        r = self.api.get("/api/articles/?q=Item 1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all("Item 1" in a["prod_name"] for a in r.json()["results"]))
        self.assertEqual(self.api.get("/api/articles/5/").json()["article_id"], 5)
        self.assertIn("colour", self.api.get("/api/articles/facets/").json())

    @mock.patch("shop.inference.popular", return_value=[20, 21, 22])
    @mock.patch("shop.inference.recommend")
    def test_feed_splits_rows(self, rec, _pop):
        rec.return_value = {"model_version": "3", "fallback": False, "items": [
            {"article_id": 1, "score": .9, "sources": ["rep"], "reason": "You bought this before"},
            {"article_id": 2, "score": .8, "sources": ["tt"], "reason": "Matches your style"},
        ]}
        body = self.api.post("/api/feed/", {"customer_id": "abc"}, format="json").json()
        rows = {r["key"]: r for r in body["rows"]}
        self.assertEqual([a["article_id"] for a in rows["buy_again"]["items"]], [1])
        self.assertEqual([a["article_id"] for a in rows["for_you"]["items"]], [2])
        self.assertEqual(rows["for_you"]["items"][0]["reason"], "Matches your style")
        self.assertEqual(rec.call_args.kwargs["age"], 30)

    @mock.patch("shop.inference.recommend", side_effect=InferenceUnavailable("down"))
    def test_feed_falls_back_when_inference_is_down(self, _rec):
        body = self.api.post("/api/feed/", {}, format="json").json()
        self.assertTrue(body["fallback"])
        self.assertEqual(body["rows"][0]["items"][0]["article_id"], 1)  # best seller first

    def test_events_bulk_and_checkout(self):
        r = self.api.post("/api/events/", [
            {"session_id": "s1", "article_id": 3, "event_type": "impression", "placement": "for_you"},
            {"session_id": "s1", "article_id": 3, "event_type": "click", "placement": "for_you"},
        ], format="json")
        self.assertEqual(r.status_code, 201)
        r = self.api.post("/api/checkout/", {"session_id": "s1", "customer_id": "abc", "article_ids": [3, 4]},
                          format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["total"], "19.98")
        self.assertEqual(Purchase.objects.filter(customer=self.cust).count(), 3)
        self.assertEqual(Event.objects.filter(event_type="purchase").count(), 2)

    def test_invalid_event_rejected(self):
        r = self.api.post("/api/events/", {"session_id": "s", "event_type": "hover"}, format="json")
        self.assertEqual(r.status_code, 400)

    @mock.patch("shop.inference.stats", return_value={"latency_ms": {}})
    @mock.patch("shop.inference.model_info", return_value={"metrics": {}})
    def test_ops_requires_token_and_reports_ctr(self, *_):
        self.assertEqual(self.api.get("/api/ops/overview/").status_code, 403)
        Event.objects.create(session_id="s", event_type="impression", placement="for_you")
        Event.objects.create(session_id="s", event_type="impression", placement="for_you")
        Event.objects.create(session_id="s", event_type="click", placement="for_you")
        body = self.api.get("/api/ops/overview/", HTTP_X_OPS_TOKEN="t0k").json()
        self.assertEqual(body["engagement"][0]["ctr"], 0.5)
        self.assertEqual(body["inference_status"], "ok")
