"""JSON logs and a request id on every response."""

import json
import logging
import os
import uuid
from collections.abc import MutableMapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("landfall")

_SECRET_ENV = (
    "ADMIN_TOKEN",
    "PUBLISHER_SALT",
    "OPENFDA_API_KEY",
    "OPENROUTER_API_KEY",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        return json.dumps(payload, default=str)


def redact(text: str) -> str:
    cleaned = text
    for name in _SECRET_ENV:
        value = os.environ.get(name, "").strip()
        if value:
            cleaned = cleaned.replace(value, "[redacted]")
    return cleaned


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request failed", extra={"request_id": request_id})
            raise
        response.headers["X-Request-Id"] = request_id
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                }
            )
        )
        return response


def request_id_from(scope: MutableMapping) -> str | None:
    state = scope.get("state")
    if state is None:
        return None
    return getattr(state, "request_id", None)
