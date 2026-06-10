"""FastAPI entry point. The app is a thin AWS-facing shim for the web app:
artifact reads (S3 or the local runs directory) plus admin control of the
daily engine run. Credentials come from the boto3 default chain; locally the
stack runs against DynamoDB local and the runs directory with no AWS at all.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from wolves_backend.config import Settings, get_settings
from wolves_backend.deps import Deps, build_deps
from wolves_backend.errors import UpstreamError
from wolves_backend.routes.admin import router as admin_router
from wolves_backend.routes.agent_state import router as agent_state_router
from wolves_backend.routes.health import router as health_router
from wolves_backend.routes.odds import router as odds_router
from wolves_backend.routes.runs import router as runs_router
from wolves_backend.routes.snapshots import router as snapshots_router
from wolves_backend.routes.teams import router as teams_router

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

request_logger = logging.getLogger("wolves_backend.access")


def create_app(settings: Settings | None = None, *, deps: Deps | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Wolves forecaster API", version="0.1.0")
    app.state.settings = settings
    app.state.deps = deps or build_deps(settings)

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        request_logger.info("%s %s %d %.1fms", request.method, request.url.path, response.status_code, duration_ms)
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{location}: {first['msg']}" if location else str(first["msg"])
        return JSONResponse(status_code=400, content={"error": message})

    @app.exception_handler(UpstreamError)
    async def upstream_error(request: Request, exc: UpstreamError) -> JSONResponse:
        request_logger.warning("Upstream %s failure on %s: %s", exc.service, request.url.path, exc.detail)
        return JSONResponse(status_code=502, content={"error": exc.detail})

    app.include_router(health_router)
    app.include_router(snapshots_router)
    app.include_router(runs_router)
    app.include_router(teams_router)
    app.include_router(agent_state_router)
    app.include_router(odds_router)
    app.include_router(admin_router)
    return app


def build() -> FastAPI:
    """Uvicorn factory: configures logging once, then builds the app."""
    settings = get_settings()
    # Uvicorn does not configure app loggers; without basicConfig, INFO falls
    # through to lastResort at WARNING.
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return create_app(settings)
