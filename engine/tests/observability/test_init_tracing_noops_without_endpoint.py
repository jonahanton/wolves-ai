from opentelemetry import trace

from wolves.observability import tracing


def test_init_without_endpoint_leaves_global_provider_untouched(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(tracing, "_initialised", False)

    before = trace.get_tracer_provider()
    tracing.init_tracing()

    assert tracing._initialised is False
    assert trace.get_tracer_provider() is before


def test_init_is_idempotent_once_initialised(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    monkeypatch.setattr(tracing, "_initialised", True)

    before = trace.get_tracer_provider()
    tracing.init_tracing()

    assert trace.get_tracer_provider() is before
