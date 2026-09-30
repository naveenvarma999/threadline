"""Threadline inference service (FastAPI).

Endpoints are plain ``def`` functions: scoring is CPU-bound, so FastAPI runs them in its
thread pool and the event loop stays free for health checks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.cache import make_cache
from app.model import ModelState
from app.settings import settings
from app.stats import Stats

logging.basicConfig(level=settings.log_level, format="%(message)s")
log = logging.getLogger("inference")

state = ModelState()
stats = Stats()
cache = make_cache(settings.redis_url, settings.cache_ttl_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    state.load(settings)
    if state.recommender is None:
        # No model yet (e.g. first deploy before training finished): keep retrying in the background.
        def retry() -> None:
            while state.recommender is None:
                time.sleep(30)
                state.load(settings)

        threading.Thread(target=retry, daemon=True, name="model-retry").start()
    yield


app = FastAPI(title="Threadline inference", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path
    if endpoint not in ("/health", "/stats"):
        stats.observe(endpoint, ms)
    response.headers["x-request-id"] = rid
    response.headers["x-model-version"] = state.version
    log.info(json.dumps({"rid": rid, "method": request.method, "path": request.url.path,
                         "status": response.status_code, "ms": round(ms, 2), "model": state.version}))
    return response


# ---------------------------------------------------------------------------- schemas
class RecommendRequest(BaseModel):
    customer_id: str | None = Field(None, description="Known customer id; omit for anonymous shoppers")
    k: int = Field(12, ge=1, le=50)
    recent_article_ids: list[int] = Field(default_factory=list, max_length=50,
                                          description="Items viewed or bought this session, newest first")
    age: float | None = Field(None, ge=10, le=100, description="Used for anonymous shoppers only")
    exclude: list[int] = Field(default_factory=list, max_length=200)


class Item(BaseModel):
    article_id: int
    score: float
    sources: list[str] = []
    reason: str = ""


class RecommendResponse(BaseModel):
    customer_id: str | None
    model_version: str
    fallback: bool
    cached: bool
    items: list[Item]


class ScoredItem(BaseModel):
    article_id: int
    score: float


# ---------------------------------------------------------------------------- helpers
def _rec():
    rec = state.recommender
    if rec is None:
        raise HTTPException(503, detail=f"Model not loaded: {state.error or 'starting'}")
    return rec


def _cache_key(req: RecommendRequest) -> str:
    body = json.dumps(req.model_dump(), sort_keys=True)
    return f"rec:{state.version}:{hashlib.sha1(body.encode()).hexdigest()}"


# ---------------------------------------------------------------------------- routes
@app.get("/health")
def health():
    ok = state.recommender is not None
    body = {"status": "ok" if ok else "degraded", "model_loaded": ok, "model_version": state.version,
            "error": state.error}
    return JSONResponse(body, status_code=200 if ok else 503)


@app.get("/model")
def model_info():
    rec = _rec()
    md = rec.metadata
    return {"registry": state.info, "data_source": md.get("data_source"), "created_at": md.get("created_at"),
            "serves_from": md.get("serves_from"), "metrics": md.get("metrics", {}),
            "ablation": md.get("ablation", {}), "top_features": md.get("top_features", {}),
            "n_articles": len(rec.articles), "n_customers": len(rec.customer_idx)}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    rec = _rec()
    key = _cache_key(req)
    hit = cache.get(key)
    if hit is not None:
        stats.incr("cache_hit")
        return {**hit, "cached": True}
    stats.incr("cache_miss")
    try:
        items = [Item(article_id=r.article_id, score=r.score, sources=r.sources, reason=r.reason).model_dump()
                 for r in rec.recommend(req.customer_id, k=req.k, recent_article_ids=req.recent_article_ids,
                                        age=req.age, exclude=req.exclude)]
        fallback = False
    except Exception:
        # Graceful degradation: never show an empty page because the ranker failed.
        log.exception("recommend failed; serving popular items")
        stats.incr("fallback")
        excluded = set(req.exclude)
        items = [Item(article_id=a, score=0.0, sources=["pop"], reason="Trending now").model_dump()
                 for a in rec.popular(req.k + len(excluded), req.age) if a not in excluded][: req.k]
        fallback = True
    body = {"customer_id": req.customer_id, "model_version": state.version, "fallback": fallback, "items": items}
    if not fallback:
        cache.set(key, body)
    return {**body, "cached": False}


@app.get("/similar/{article_id}", response_model=list[ScoredItem])
def similar(article_id: int, k: int = Query(12, ge=1, le=50)):
    out = _rec().similar(article_id, k)
    if not out:
        raise HTTPException(404, detail=f"Unknown article {article_id}")
    return [{"article_id": a, "score": s} for a, s in out]


@app.get("/bought-together/{article_id}", response_model=list[ScoredItem])
def bought_together(article_id: int, k: int = Query(6, ge=1, le=20)):
    return [{"article_id": a, "score": s} for a, s in _rec().bought_together(article_id, k)]


@app.get("/popular", response_model=list[int])
def popular(k: int = Query(12, ge=1, le=50), age: float | None = Query(None, ge=10, le=100)):
    return _rec().popular(k, age)


@app.get("/stats")
def service_stats():
    return {**stats.snapshot(), "model_version": state.version}


@app.post("/admin/reload")
def reload(x_admin_token: str = Header("")):
    """Hot-swap to whatever the registry alias points at now (called after a promotion)."""
    if x_admin_token != settings.admin_token:
        raise HTTPException(401, detail="Invalid admin token")
    before = state.version
    state.load(settings)
    cache.clear()
    return {"previous_version": before, "model_version": state.version, "error": state.error}
