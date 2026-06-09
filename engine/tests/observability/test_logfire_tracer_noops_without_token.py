from __future__ import annotations

from wolves.config import Settings
from wolves.observability import build_logfire_tracer


def test_tracer_opens_spans_offline_with_no_token():
    tracer = build_logfire_tracer(Settings(logfire_token=""))

    assert tracer.current_trace_id() is None

    with tracer.observation("outer", as_type="agent") as span:
        assert span.trace_id and span.id
        assert tracer.current_trace_id() == span.trace_id
        span.update(output={"ok": True}, metadata={"k": "v"})
        with tracer.observation("inner", as_type="generation", model="m") as inner:
            assert inner.trace_id == span.trace_id
            assert inner.id != span.id

    assert tracer.current_trace_id() is None
    tracer.flush()
