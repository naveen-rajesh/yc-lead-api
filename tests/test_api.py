from fastapi.testclient import TestClient

from api.main import DEFAULT_DEMO_KEY, app


client = TestClient(app)
headers = {"X-API-Key": DEFAULT_DEMO_KEY}


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_companies_requires_key():
    response = client.get("/companies")
    assert response.status_code == 401


def test_companies_search_and_pagination():
    response = client.get("/companies?q=airbnb&limit=5", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["total"] >= 1
    assert body["results"][0]["name"] == "Airbnb"


def test_metadata_returns_facets():
    response = client.get("/metadata", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["companies"] > 0
    assert "Consumer" in body["industries"]


def test_high_value_leads_have_scores():
    response = client.get("/leads/high-value?limit=3", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) <= 3
    assert body["results"][0]["lead_score"] >= body["results"][-1]["lead_score"]


def test_rapidapi_proxy_secret(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "test-secret")
    response = client.get(
        "/companies?limit=1",
        headers={
            "X-RapidAPI-Key": "rapidapi-user-key",
            "X-RapidAPI-Proxy-Secret": "test-secret",
        },
    )
    assert response.status_code == 200
    assert response.json()["auth_source"] == "rapidapi"


def test_rapidapi_key_without_proxy_secret(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_PROXY_SECRET", raising=False)
    response = client.get(
        "/companies?limit=1",
        headers={"X-RapidAPI-Key": "rapidapi-user-key"},
    )
    assert response.status_code == 200
    assert response.json()["auth_source"] == "rapidapi"


def test_rapidapi_wrong_proxy_secret(monkeypatch):
    monkeypatch.setenv("RAPIDAPI_PROXY_SECRET", "test-secret")
    response = client.get(
        "/companies?limit=1",
        headers={
            "X-RapidAPI-Key": "rapidapi-user-key",
            "X-RapidAPI-Proxy-Secret": "wrong-secret",
        },
    )
    assert response.status_code == 403
