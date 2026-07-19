"""FastAPI application factory and operational endpoints."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from sqlalchemy import text
from starlette.staticfiles import StaticFiles

from dataset_foundry import __version__
from dataset_foundry.api.errors import install_error_handlers
from dataset_foundry.api.middleware import RequestContextMiddleware
from dataset_foundry.api.routes import router
from dataset_foundry.container import Container, get_container


def create_app(container: Container | None = None) -> FastAPI:
    dependencies = container or get_container()
    app = FastAPI(
        title="Dataset Foundry API",
        version=__version__,
        description="Local-first synthetic fine-tuning data generation and quality review.",
    )
    app.state.container = dependencies
    app.add_middleware(RequestContextMiddleware, settings=dependencies.settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=dependencies.settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    frontend_dist = dependencies.settings.frontend_dist.resolve()
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "dataset-foundry",
            "version": __version__,
        }

    @app.get("/ready")
    def ready(request: Request) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        try:
            with dependencies.database.session() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                {
                    "status": "not_ready",
                    "database": "error",
                    "request_id": request_id,
                },
                status_code=503,
            )
        return JSONResponse({"status": "ready", "database": "ok", "request_id": request_id})

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        runs = dependencies.repositories.runs.list(limit=10_000)
        projects = dependencies.repositories.projects.list(limit=10_000)
        datasets = dependencies.repositories.datasets.list(limit=10_000)
        lines = [
            "# TYPE dataset_foundry_projects gauge",
            f"dataset_foundry_projects {len(projects)}",
            "# TYPE dataset_foundry_datasets gauge",
            f"dataset_foundry_datasets {len(datasets)}",
            "# TYPE dataset_foundry_runs gauge",
            f"dataset_foundry_runs {len(runs)}",
        ]
        for status in ("queued", "running", "completed", "failed", "cancelled"):
            count = sum(run.status == status for run in runs)
            lines.append(f'dataset_foundry_runs_by_status{{status="{status}"}} {count}')
        return "\n".join(lines) + "\n"

    app.include_router(router)

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str, request: Request) -> Response:
        reserved = {"health", "ready", "metrics", "openapi.json"}
        if full_path.startswith("api/") or full_path in reserved:
            return JSONResponse(
                {
                    "type": "about:blank",
                    "title": "Not found",
                    "status": 404,
                    "detail": "The requested route does not exist.",
                    "instance": request.url.path,
                    "request_id": getattr(request.state, "request_id", "unknown"),
                },
                status_code=404,
                media_type="application/problem+json",
            )
        requested = (frontend_dist / full_path).resolve()
        if full_path and requested.is_relative_to(frontend_dist) and requested.is_file():
            return FileResponse(requested)
        index = frontend_dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {
                "status": "api_only",
                "detail": "Build frontend assets to enable the workbench.",
            },
            status_code=404,
        )

    return app


app = create_app()
