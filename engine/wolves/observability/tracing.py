"""OpenTelemetry tracing bootstrap.

Reads the standard OTel environment contract (OTEL_EXPORTER_OTLP_ENDPOINT,
OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES) directly rather than Settings so
any collector that injects those variables works unmodified. When the endpoint
is unset or the SDK is absent every function is a clean no-op, so importing
this module costs nothing outside traced deployments.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_initialised = False


def init_tracing(service_name: str | None = None) -> None:
    """Initialise the global OTLP tracer provider once; later calls return immediately."""
    global _initialised
    if _initialised:
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set; tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.debug("OpenTelemetry SDK not installed; tracing disabled (install wolves[otel])")
        return

    resolved_name = service_name or os.environ.get("OTEL_SERVICE_NAME") or "wolves-engine"

    # Resource.create merges OTEL_RESOURCE_ATTRIBUTES from the environment.
    provider = TracerProvider(resource=Resource.create({"service.name": resolved_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    _instrument_httpx()
    _instrument_botocore()

    _initialised = True
    logger.info("OpenTelemetry tracing initialised (service=%s)", resolved_name)


def get_tracer(name: str) -> Any:
    """Return a tracer for manual spans; a no-op tracer when OTel is absent."""
    try:
        from opentelemetry import trace
    except ImportError:
        return _NoOpTracer()
    return trace.get_tracer(name)


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    except ImportError:
        logger.debug("httpx instrumentation not installed; skipping")
        return
    HTTPXClientInstrumentor().instrument()


def _instrument_botocore() -> None:
    try:
        from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    except ImportError:
        logger.debug("botocore instrumentation not installed; skipping")
        return
    BotocoreInstrumentor().instrument()


class _NoOpSpan:
    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def set_attribute(self, key: str, value: object) -> None:
        return None


class _NoOpTracer:
    def start_as_current_span(self, name: str, **kwargs: object) -> _NoOpSpan:
        return _NoOpSpan()
