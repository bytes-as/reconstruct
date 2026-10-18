"""G005: every response carries X-Request-Id and a log line contains it."""

import logging

from fastapi.testclient import TestClient

from app.logging import redact
from app.main import create_app


def test_response_and_log_carry_request_id(caplog) -> None:
    caplog.set_level(logging.INFO, logger="landfall")
    app = create_app()
    logging.getLogger().addHandler(caplog.handler)
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"X-Request-Id": "req-test-1"})
    assert response.headers["X-Request-Id"] == "req-test-1"
    assert "req-test-1" in caplog.text


def test_secret_values_are_redacted() -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    text = redact(f"token {settings.admin_token} salt {settings.publisher_salt}")
    assert settings.admin_token not in text
    assert settings.publisher_salt not in text
    assert "[redacted]" in text
