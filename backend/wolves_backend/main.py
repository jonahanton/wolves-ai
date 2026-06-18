"""FastAPI entry point. The app is a thin AWS-facing shim for the web app:
artifact reads (S3 or the local runs directory) plus admin control of the
daily engine run. Credentials come from the boto3 default chain; locally the
stack runs against DynamoDB local and the runs directory with no AWS at all.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from wolves_backend.access_log import access_log_line
from wolves_backend.auth import FRONTEND_KEY_HEADER, has_frontend_key, is_admin
from wolves_backend.clients.alerts import Alerts
from wolves_backend.config import Settings, get_settings
from wolves_backend.deps import Deps, build_deps
from wolves_backend.errors import UpstreamError
from wolves_backend.jobs import ArchiveLoop, LiveLoop
from wolves_backend.routes.admin import router as admin_router
from wolves_backend.routes.agent_state import router as agent_state_router
from wolves_backend.routes.health import router as health_router
from wolves_backend.routes.impact import router as impact_router
from wolves_backend.routes.live import router as live_router
from wolves_backend.routes.market import router as market_router
from wolves_backend.routes.odds import router as odds_router
from wolves_backend.routes.results import router as results_router
from wolves_backend.routes.runs import router as runs_router
from wolves_backend.routes.simulate import router as simulate_router
from wolves_backend.routes.snapshots import router as snapshots_router
from wolves_backend.routes.teams import router as teams_router
from wolves_backend.sim import EngineNotReadyError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("wolves_backend.access")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    deps: Deps = app.state.deps
    alerts = Alerts(topic_arn=settings.alerts_topic_arn, region=settings.aws_region)
    tasks = [asyncio.create_task(deps.engine.run(refresh_interval_s=settings.engine_refresh_interval_s))]
    if settings.jobs_enabled:
        archive = ArchiveLoop(engine=deps.engine, alerts=alerts, hours=settings.archive_hours)
        tasks.append(asyncio.create_task(LiveLoop(deps=deps, alerts=alerts).run()))
        tasks.append(asyncio.create_task(archive.run()))
    else:
        logger.info("in-process jobs disabled (JOBS_ENABLED=0); live and archive loops parked")
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


def create_app(settings: Settings | None = None, *, deps: Deps | None = None) -> FastAPI:
    settings = settings or get_settings()
    expose_docs = settings.environment == "local"
    app = FastAPI(
        title="Wolves forecaster API",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    app.state.settings = settings
    app.state.deps = deps or build_deps(settings)

    @app.middleware("http")
    async def require_frontend_key(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method != "OPTIONS" and request.url.path != "/healthz" and not has_frontend_key(settings, request):
            return JSONResponse(
                status_code=401,
                content={"error": "authentication required"},
                headers={"WWW-Authenticate": FRONTEND_KEY_HEADER},
            )
        return await call_next(request)

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        if request.url.path == "/healthz":
            return response
        access_logger.info(
            access_log_line(
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=(time.monotonic() - start) * 1000,
                client_ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                admin=is_admin(settings, request),
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"error": str(exc.detail)}, headers=exc.headers or None
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = f"{location}: {first['msg']}" if location else str(first["msg"])
        return JSONResponse(status_code=400, content={"error": message})

    @app.exception_handler(UpstreamError)
    async def upstream_error(request: Request, exc: UpstreamError) -> JSONResponse:
        logger.warning("Upstream %s failure on %s: %s", exc.service, request.url.path, exc.detail)
        return JSONResponse(status_code=502, content={"error": exc.detail})

    @app.exception_handler(EngineNotReadyError)
    async def engine_not_ready(_request: Request, exc: EngineNotReadyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"error": str(exc)})

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": "internal server error"})

    app.include_router(health_router)
    app.include_router(simulate_router)
    app.include_router(results_router)
    app.include_router(impact_router)
    app.include_router(live_router)
    app.include_router(snapshots_router)
    app.include_router(runs_router)
    app.include_router(teams_router)
    app.include_router(agent_state_router)
    app.include_router(market_router)
    app.include_router(odds_router)
    app.include_router(admin_router)
    return app


def build() -> FastAPI:
    """Uvicorn factory: configures logging once, then builds the app."""
    settings = get_settings()
    # Uvicorn does not configure app loggers; without basicConfig, INFO falls
    # through to lastResort at WARNING.
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Access lines are already structured JSON, so they go to stdout bare
    # rather than through the prefixed stderr handler.
    access_logger.addHandler(logging.StreamHandler(sys.stdout))
    access_logger.propagate = False
    return create_app(settings)
