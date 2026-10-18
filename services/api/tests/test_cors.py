"""G007: CORS allows only CORS_ORIGINS."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_disallowed_origin_has_no_cors_header(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3001")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in {key.lower() for key in response.headers}


def test_allowed_origin_is_echoed(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3001")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": "http://localhost:3001"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3001"
