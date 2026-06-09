from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wolves.observability.budget import BudgetState, Caps
from wolves.observability.events import EventLog
from wolves.observability.tracer import SpanHandle, Tracer

# Semantic observation types carried as span attributes so the trace UI can
# distinguish agent turns, generations, retrievals and tool calls.
_OBSERVATION_TYPES = {
    "run": "agent",
    "llm_call": "generation",
    "research": "retriever",
    "forecast": "agent",
    "critic": "agent",
    "synthesise": "agent",
    "web_search": "tool",
    "fetch": "tool",
    "data_fetch": "retriever",
    "workspace_write": "tool",
    "quant": "tool",
    "quant_exec": "tool",
    "final_answer": "chain",
}


class CapExceeded(RuntimeError):
    """Raised when a hard cap would be exceeded by an external action."""


@dataclass
class RunPaths:
    root: Path
    events: Path
    state: Path
    workspace: Path

    @classmethod
    def for_run(cls, runs_root: Path, run_id: str) -> RunPaths:
        root = runs_root / run_id
        workspace = root / "workspace"
        for sub in ("raw", "derived", "models", "quant"):
            (workspace / sub).mkdir(parents=True, exist_ok=True)
        return cls(root=root, events=root / "events.jsonl", state=root / "state.json", workspace=workspace)


class Recorder:
    """Yielded inside `observe`. Enriches both the tracer span and JSONL event."""

    def __init__(self, span: SpanHandle) -> None:
        self._span = span
        self.summary = ""
        self.payload: dict[str, Any] = {}

    @property
    def trace_id(self) -> str | None:
        return self._span.trace_id

    @property
    def observation_id(self) -> str | None:
        return self._span.id

    def set_output(
        self,
        output: Any,
        *,
        usage: dict[str, int] | None = None,
        cost: dict[str, float] | None = None,
        model: str | None = None,
    ) -> None:
        self._span.update(output=output, usage=usage, cost=cost, model=model)

    def annotate(self, **metadata: Any) -> None:
        self._span.update(metadata=metadata)

    def note(self, summary: str | None = None, **payload: Any) -> None:
        """Record fields for the local JSONL mirror (and human-readable tail)."""
        if summary is not None:
            self.summary = summary
        self.payload.update(payload)


class ObservedRuntime:
    """The single place that talks to the tracer and the local event stream, and
    the single gatekeeper that enforces caps before any external action."""

    def __init__(
        self,
        *,
        run_id: str,
        tracer: Tracer,
        events: EventLog,
        caps: Caps,
        paths: RunPaths,
    ) -> None:
        self.run_id = run_id
        self.tracer = tracer
        self.events = events
        self.caps = caps
        self.paths = paths
        self.budget = BudgetState()

    @contextlib.contextmanager
    def observe(
        self,
        *,
        kind: str,
        actor: str,
        name: str | None = None,
        as_generation: bool = False,
        model: str | None = None,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
        model_parameters: dict[str, Any] | None = None,
    ) -> Iterator[Recorder]:
        span_name = name or f"{kind}:{actor}"
        as_type = "generation" if as_generation else _OBSERVATION_TYPES.get(kind, "span")
        with self.tracer.observation(
            span_name,
            as_type=as_type,
            model=model,
            input=input,
            metadata=metadata,
            model_parameters=model_parameters,
        ) as span:
            recorder = Recorder(span)
            try:
                yield recorder
            except Exception as exc:
                recorder.note(error=f"{type(exc).__name__}: {exc}")
                span.update(metadata={"error": str(exc)})
                raise
            finally:
                self.events.append(
                    kind=kind,
                    actor=actor,
                    summary=recorder.summary,
                    payload=recorder.payload,
                    trace_id=recorder.trace_id,
                    observation_id=recorder.observation_id,
                )

    @contextlib.contextmanager
    def run_trace(self, *, title: str = "") -> Iterator[Recorder]:
        with self.observe(
            kind="run",
            actor="runtime",
            name=f"run:{self.run_id}",
            input={"title": title} if title else None,
        ) as recorder:
            yield recorder

    def emit(self, kind: str, actor: str, summary: str, **payload: Any) -> None:
        """A point-in-time event: a short tracer observation mirrored to JSONL."""
        as_type = _OBSERVATION_TYPES.get(kind, "span")
        with self.tracer.observation(f"{kind}:{actor}", as_type=as_type, input=payload) as span:
            span.update(output={"summary": summary})
            self.events.append(
                kind=kind,
                actor=actor,
                summary=summary,
                payload=payload,
                trace_id=span.trace_id,
                observation_id=span.id,
            )

    def require_active_observation(self) -> None:
        if self.tracer.current_trace_id() is None:
            raise RuntimeError("Refusing external action with no active observation.")

    def charge_llm(self) -> None:
        self.require_active_observation()
        if self.budget.llm_calls >= self.caps.max_llm_calls:
            raise CapExceeded(f"max_llm_calls ({self.caps.max_llm_calls}) reached")
        if self.caps.max_cost_micros and self.budget.cost_micros >= self.caps.max_cost_micros:
            raise CapExceeded(f"max_cost_micros ({self.caps.max_cost_micros}) reached")
        self.budget.llm_calls += 1

    def charge_search(self) -> None:
        self.require_active_observation()
        if self.budget.search_calls >= self.caps.max_search_calls:
            raise CapExceeded(f"max_search_calls ({self.caps.max_search_calls}) reached")
        self.budget.search_calls += 1

    def charge_fetch(self) -> None:
        self.require_active_observation()
        if self.budget.fetch_calls >= self.caps.max_fetch_calls:
            raise CapExceeded(f"max_fetch_calls ({self.caps.max_fetch_calls}) reached")
        self.budget.fetch_calls += 1

    def charge_data_fetch(self) -> None:
        self.require_active_observation()
        if self.budget.data_fetches >= self.caps.max_data_fetches:
            raise CapExceeded(f"max_data_fetches ({self.caps.max_data_fetches}) reached")
        self.budget.data_fetches += 1

    def charge_quant(self) -> None:
        self.require_active_observation()
        if self.budget.quant_executions >= self.caps.max_quant_executions:
            raise CapExceeded(f"max_quant_executions ({self.caps.max_quant_executions}) reached")
        self.budget.quant_executions += 1

    def add_cost(self, micros: int) -> None:
        self.budget.cost_micros += micros

    def bump_iteration(self) -> int:
        self.budget.iterations += 1
        return self.budget.iterations

    def snapshot(self) -> BudgetState:
        return self.budget.model_copy()

    def shutdown(self) -> None:
        with contextlib.suppress(Exception):
            self.tracer.flush()
        with contextlib.suppress(Exception):
            self.tracer.shutdown()
        self.events.close()


def build_runtime(
    *,
    run_id: str,
    tracer: Tracer,
    caps: Caps,
    runs_root: Path,
) -> ObservedRuntime:
    """Wire a runtime for one run: paths, JSONL event log and the given tracer."""
    paths = RunPaths.for_run(runs_root, run_id)
    events = EventLog(run_id, paths.events)
    return ObservedRuntime(run_id=run_id, tracer=tracer, events=events, caps=caps, paths=paths)
