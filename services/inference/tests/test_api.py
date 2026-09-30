import pandas as pd


def _customer(client):
    return pd.read_parquet(client.bundle / "snapshot" / "history.parquet")["customer_idx"].iloc[0], \
        pd.read_parquet(client.bundle / "customers.parquet")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["model_loaded"] is True
    assert "x-request-id" in r.headers


def test_recommend_known_customer_and_cache(client):
    idx, customers = _customer(client)
    cid = customers.loc[customers["customer_idx"] == idx, "customer_id"].iloc[0]
    r = client.post("/recommend", json={"customer_id": cid, "k": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 10 and body["fallback"] is False and body["cached"] is False
    assert all(i["reason"] for i in body["items"])
    again = client.post("/recommend", json={"customer_id": cid, "k": 10}).json()
    assert again["cached"] is True and again["items"] == body["items"]


def test_anonymous_with_session_items(client):
    items = pd.read_parquet(client.bundle / "articles.parquet")["article_id"].head(2).tolist()
    r = client.post("/recommend", json={"recent_article_ids": items, "age": 28, "k": 6, "exclude": items})
    assert r.status_code == 200
    got = [i["article_id"] for i in r.json()["items"]]
    assert len(got) == 6 and not set(got) & set(items)


def test_validation_errors(client):
    assert client.post("/recommend", json={"k": 0}).status_code == 422
    assert client.post("/recommend", json={"k": 5, "age": 3}).status_code == 422


def test_similar_and_bought_together(client):
    a = int(pd.read_parquet(client.bundle / "articles.parquet")["article_id"].iloc[5])
    sim = client.get(f"/similar/{a}?k=5").json()
    assert len(sim) == 5
    assert client.get("/similar/1").status_code == 404
    assert client.get(f"/bought-together/{a}").status_code == 200


def test_fallback_when_ranker_fails(client, monkeypatch):
    import app.main as m

    def boom(*a, **k):
        raise RuntimeError("ranker exploded")

    monkeypatch.setattr(m.state.recommender, "recommend", boom)
    r = client.post("/recommend", json={"k": 4, "age": 40})
    assert r.status_code == 200
    assert r.json()["fallback"] is True and len(r.json()["items"]) == 4


def test_stats_and_model_info(client):
    s = client.get("/stats").json()
    assert "/recommend" in s["latency_ms"] and s["latency_ms"]["/recommend"]["p95"] >= 0
    info = client.get("/model").json()
    assert info["n_articles"] > 0


def test_reload_requires_token(client):
    assert client.post("/admin/reload").status_code == 401
    r = client.post("/admin/reload", headers={"x-admin-token": "change-me"})
    assert r.status_code == 200 and r.json()["error"] is None
