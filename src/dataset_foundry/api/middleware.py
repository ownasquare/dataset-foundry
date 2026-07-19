"""Request IDs and optional local API-key enforcement."""

from __future__ import annotations

import hmac
import re
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from dataset_foundry.config import Settings

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_PROTECTED_API_PATHS = frozenset(
    {
        "/docs",
        "/docs/oauth2-redirect",
        "/metrics",
        "/openapi.json",
        "/redoc",
    }
)


def _requires_api_key(path: str) -> bool:
    """Protect data and operational APIs while leaving the SPA shell readable."""

    return path in _PROTECTED_API_PATHS or path == "/api" or path.startswith("/api/")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id if _SAFE_REQUEST_ID.fullmatch(supplied_request_id) else uuid4().hex
        )
        request.state.request_id = request_id
        if self.settings.api_key is not None and _requires_api_key(request.url.path):
            expected = self.settings.api_key.get_secret_value()
            supplied = request.headers.get("x-api-key", "")
            if not hmac.compare_digest(supplied, expected):
                unauthorized = JSONResponse(
                    {
                        "type": "about:blank",
                        "title": "Unauthorized",
                        "status": 401,
                        "detail": "A valid API key is required.",
                        "instance": request.url.path,
                        "request_id": request_id,
                    },
                    status_code=401,
                    media_type="application/problem+json",
                )
                unauthorized.headers["x-request-id"] = request_id
                return unauthorized
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
