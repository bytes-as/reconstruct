"""G006: 404, 422 and 503 envelopes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import ApiError, install_error_handlers
from app.logging import RequestIdMiddleware


class NdcBody(BaseModel):
    ndc: str


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)

    @app.post("/api/check")
    def check(_body: NdcBody) -> dict:
        return {"ok": True}

    @app.get("/api/down")
    def down() -> dict:
        raise ApiError("GRAPH_UNAVAILABLE", "FalkorDB is restarting.", retry_after_s=5)

    return app


def test_not_found_envelope() -> None:
    response = TestClient(_app()).get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()["error"]
    assert body["code"] == "NOT_FOUND"
    assert body["retry_after_s"] is None
    assert response.headers["X-Request-Id"]


def test_invalid_input_envelope() -> None:
    response = TestClient(_app()).post("/api/check", json={})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "INVALID_INPUT"
    assert body["hint"]


def test_graph_unavailable_envelope() -> None:
    response = TestClient(_app()).get("/api/down")
    assert response.status_code == 503
    body = response.json()["error"]
    assert body == {
        "code": "GRAPH_UNAVAILABLE",
        "message": "FalkorDB is restarting.",
        "hint": None,
        "retry_after_s": 5,
    }
