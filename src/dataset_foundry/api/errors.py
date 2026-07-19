"""RFC 7807-style problem responses with request correlation."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dataset_foundry.ingestion import IngestionError
from dataset_foundry.persistence import RecordNotFoundError


class ApiProblem(RuntimeError):
    def __init__(self, status: int, title: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail


def _problem(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", "unknown"),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiProblem)
    async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
        return _problem(
            request,
            status=exc.status,
            title=exc.title,
            detail=exc.detail,
        )

    @app.exception_handler(RecordNotFoundError)
    async def not_found_handler(request: Request, exc: RecordNotFoundError) -> JSONResponse:
        return _problem(request, status=404, title="Not found", detail=str(exc))

    @app.exception_handler(IngestionError)
    async def ingestion_handler(request: Request, exc: IngestionError) -> JSONResponse:
        return _problem(request, status=422, title="Invalid seed dataset", detail=str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "loc": [str(value) for value in error.get("loc", ())],
                "msg": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return _problem(
            request,
            status=422,
            title="Validation error",
            detail="The request did not match the expected contract.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, _exc: Exception) -> JSONResponse:
        return _problem(
            request,
            status=500,
            title="Internal server error",
            detail="The request could not be completed. Use the request ID to inspect logs.",
        )
