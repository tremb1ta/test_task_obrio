import pytest


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_collect_reviews(test_client, mock_services):
    from app.services.scraper import ScrapeResult

    mock_services.scraper.collect.return_value = ScrapeResult(
        app_id="389801252", collected=10, new=10, duplicates=0, source="rss_feed"
    )
    resp = await test_client.post(
        "/api/v1/reviews/collect",
        json={"app_id": "389801252", "country": "us"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["collected"] == 10
    assert data["source"] == "rss_feed"


@pytest.mark.asyncio
async def test_get_reviews_empty(test_client, mock_services):
    resp = await test_client.get("/api/v1/reviews/unknown_app")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    mock_services.scraper.collect.assert_called_once()


@pytest.mark.asyncio
async def test_metrics_auto_collect(test_client, mock_services):
    resp = await test_client.get("/api/v1/metrics/unknown_app")
    assert resp.status_code == 404
    mock_services.scraper.collect.assert_called_once()


@pytest.mark.asyncio
async def test_download_json(test_client):
    resp = await test_client.get("/api/v1/reviews/test_app/download?format=json")
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_download_csv(test_client):
    resp = await test_client.get("/api/v1/reviews/test_app/download?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_rag_query_auto_collect(test_client, mock_services):
    resp = await test_client.post(
        "/api/v1/rag/query",
        json={"app_id": "unknown", "question": "What do users think?"},
    )
    assert resp.status_code == 200
    mock_services.scraper.collect.assert_called_once()
