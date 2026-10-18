"""Error envelope from API Conventions."""

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

STATUS_BY_CODE = {
    "INVALID_INPUT": 422,
    "NOT_FOUND": 404,
    "UNAUTHORIZED": 401,
    "SANDBOX_EXPIRED": 401,
    "READ_ONLY_TENANT": 403,
    "STALE_RULING": 409,
    "CHECK_NOT_CONFIRMED": 409,
    "NOT_IN_QUEUE": 409,
    "RATE_LIMITED": 429,
    "GRAPH_UNAVAILABLE": 503,
    "SOURCE_UNAVAILABLE": 503,
    "INTERNAL": 500,
}

CODE_BY_STATUS = {
    401: "UNAUTHORIZED",
    403: "READ_ONLY_TENANT",
    404: "NOT_FOUND",
    409: "STALE_RULING",
    422: "INVALID_INPUT",
    429: "RATE_LIMITED",
    500: "INTERNAL",
    503: "GRAPH_UNAVAILABLE",
}


class ApiError(Exception):
    def __init__(
        self, code: str, message: str, hint: str | None = None, retry_after_s: int | None = None
    ):
        self.code = code
        self.message = message
        self.hint = hint
        self.retry_after_s = retry_after_s
        super().__init__(message)


def envelope(
    code: str, message: str, hint: str | None = None, retry_after_s: int | None = None
) -> dict:
    return {
        "error": {"code": code, "message": message, "hint": hint, "retry_after_s": retry_after_s}
    }


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        response = JSONResponse(
            status_code=STATUS_BY_CODE[exc.code],
            content=envelope(exc.code, exc.message, exc.hint, exc.retry_after_s),
        )
        request_id = _request_id(request)
        if request_id:
            response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        hint = None
        if exc.errors():
            hint = exc.errors()[0].get("msg")
        response = JSONResponse(
            status_code=422,
            content=envelope("INVALID_INPUT", "Request validation failed.", hint),
        )
        request_id = _request_id(request)
        if request_id:
            response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(HTTPException)
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = CODE_BY_STATUS.get(exc.status_code, "INTERNAL")
        message = exc.detail if isinstance(exc.detail, str) else code
        response = JSONResponse(status_code=exc.status_code, content=envelope(code, message))
        request_id = _request_id(request)
        if request_id:
            response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        message = "The request could not be completed."
        hint = f"Request id {request_id}." if request_id else None
        response = JSONResponse(status_code=500, content=envelope("INTERNAL", message, hint))
        if request_id:
            response.headers["X-Request-Id"] = request_id
        return response
