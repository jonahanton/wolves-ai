from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wolves.config import Settings


class SpanHandle(ABC):
    """A handle to one open observation. Exposes the ids we mirror into JSONL."""

    id: str | None
    trace_id: str | None

    @abstractmethod
    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        cost: dict[str, float] | None = None,
        model: str | None = None,
    ) -> None: ...


class Tracer(ABC):
    """The only observability seam the rest of the code depends on. The real
    implementation talks to Logfire; tests use the in-memory implementation."""

    @abstractmethod
    def observation(
        self,
        name: str,
        *,
        as_type: str = "span",
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> contextlib.AbstractContextManager[SpanHandle]: ...

    @abstractmethod
    def current_trace_id(self) -> str | None: ...

    @abstractmethod
    def flush(self) -> None: ...

    @abstractmethod
    def shutdown(self) -> None: ...


class _LogfireSpan(SpanHandle):
    def __init__(self, span: Any) -> None:
        self._span = span
        context = span.get_span_context() if hasattr(span, "get_span_context") else None
        if context is not None and context.span_id:
            self.id = format(context.span_id, "016x")
            self.trace_id = format(context.trace_id, "032x")
        else:
            self.id = None
            self.trace_id = None

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        cost: dict[str, float] | None = None,
        model: str | None = None,
    ) -> None:
        if output is not None:
            self._span.set_attribute("output", output)
        if metadata:
            for key, value in metadata.items():
                self._span.set_attribute(f"metadata.{key}", value)
        if usage:
            self._span.set_attribute("usage", usage)
        if cost:
            self._span.set_attribute("cost", cost)
        if model:
            self._span.set_attribute("model", model)


class LogfireTracer(Tracer):
    """Logfire-backed tracer. Without a token, spans still open locally so trace
    ids and the JSONL mirror keep working; nothing is sent anywhere."""

    def __init__(self, logfire_module: Any) -> None:
        self._logfire = logfire_module

    @contextlib.contextmanager
    def observation(
        self,
        name: str,
        *,
        as_type: str = "span",
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> Iterator[SpanHandle]:
        attributes: dict[str, Any] = {"observation_type": as_type}
        if model:
            attributes["model"] = model
        if input is not None:
            attributes["input"] = input
        if metadata:
            attributes.update({f"metadata.{k}": v for k, v in metadata.items()})
        if model_parameters:
            attributes["model_parameters"] = model_parameters
        with self._logfire.span(name, **attributes) as span:
            yield _LogfireSpan(span)

    def current_trace_id(self) -> str | None:
        from opentelemetry import trace as otel_trace

        context = otel_trace.get_current_span().get_span_context()
        return format(context.trace_id, "032x") if context.trace_id else None

    def flush(self) -> None:
        self._logfire.force_flush()

    def shutdown(self) -> None:
        self._logfire.shutdown()


def build_logfire_tracer(settings: Settings) -> LogfireTracer:
    import logfire

    logfire.configure(
        token=settings.logfire_token or None,
        send_to_logfire="if-token-present",
        service_name="wolves-engine",
        console=False,
    )
    return LogfireTracer(logfire)


@dataclass
class SpanRecord:
    id: str
    trace_id: str
    name: str
    as_type: str
    parent_id: str | None = None
    input: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    output: Any | None = None
    usage: dict[str, int] | None = None
    cost: dict[str, float] | None = None


class _MemSpan(SpanHandle):
    def __init__(self, record: SpanRecord) -> None:
        self._record = record
        self.id = record.id
        self.trace_id = record.trace_id

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        cost: dict[str, float] | None = None,
        model: str | None = None,
    ) -> None:
        if output is not None:
            self._record.output = output
        if metadata:
            self._record.metadata.update(metadata)
        # Mirror the real backend: usage/cost/model are only kept on generations.
        if self._record.as_type == "generation":
            if usage:
                self._record.usage = usage
            if cost:
                self._record.cost = cost
            if model:
                self._record.model = model


class InMemoryTracer(Tracer):
    """Records every observation in memory. Same interface as the real tracer."""

    def __init__(self, trace_id: str = "trace-test") -> None:
        self._trace_id = trace_id
        self.spans: list[SpanRecord] = []
        self._stack: list[str] = []
        self._n = 0

    @contextlib.contextmanager
    def observation(
        self,
        name: str,
        *,
        as_type: str = "span",
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> Iterator[SpanHandle]:
        self._n += 1
        record = SpanRecord(
            id=f"obs-{self._n}",
            trace_id=self._trace_id,
            name=name,
            as_type=as_type,
            parent_id=self._stack[-1] if self._stack else None,
            input=input,
            metadata=dict(metadata or {}),
            model=model,
        )
        self.spans.append(record)
        self._stack.append(record.id)
        try:
            yield _MemSpan(record)
        finally:
            self._stack.pop()

    def current_trace_id(self) -> str | None:
        return self._trace_id if self._stack else None

    def flush(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def by_name(self, name: str) -> list[SpanRecord]:
        return [s for s in self.spans if s.name == name]

    def generations(self) -> list[SpanRecord]:
        return [s for s in self.spans if s.as_type == "generation"]
