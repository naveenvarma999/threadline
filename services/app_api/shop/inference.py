"""Thin HTTP client for the inference service. Every call has a timeout and a safe fallback."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

log = logging.getLogger(__name__)


class InferenceUnavailable(Exception):
    pass


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.INFERENCE_URL, timeout=settings.INFERENCE_TIMEOUT_SECONDS)


def _call(method: str, path: str, **kw):
    try:
        with _client() as c:
            r = c.request(method, path, **kw)
            r.raise_for_status()
            return r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.warning("inference %s %s failed: %s", method, path, e)
        raise InferenceUnavailable(str(e)) from e


def recommend(customer_id: str | None, k: int, recent: list[int], age: float | None, exclude: list[int]) -> dict:
    return _call("POST", "/recommend", json={"customer_id": customer_id, "k": k, "recent_article_ids": recent,
                                              "age": age, "exclude": exclude})


def popular(k: int, age: float | None) -> list[int]:
    params = {"k": k} | ({"age": age} if age else {})
    return _call("GET", "/popular", params=params)


def similar(article_id: int, k: int) -> list[dict]:
    return _call("GET", f"/similar/{article_id}", params={"k": k})


def bought_together(article_id: int, k: int) -> list[dict]:
    return _call("GET", f"/bought-together/{article_id}", params={"k": k})


def model_info() -> dict:
    return _call("GET", "/model")


def stats() -> dict:
    return _call("GET", "/stats")


def reload_model() -> dict:
    return _call("POST", "/admin/reload", headers={"x-admin-token": settings.INFERENCE_ADMIN_TOKEN})
