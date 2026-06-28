from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wolves.observability.budget import BudgetState, Caps
from wolves.observability.events import EventLog
from wolves.observability.tracer import SpanHandle, Tracer
from wolves.s3.layout import run_dir

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
    "tool_call": "tool",
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
        root = run_dir(runs_root, run_id)
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


_DEFAULT_CALL_ESTIMATE_MICROS = 50_000


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
        self._in_flight_micros = 0
        self._settled_cost_micros = 0
        self._settled_calls = 0

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
                span.update(metadata={"error": str(exc), "severity": "error"})
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

    def emit(self, kind: str, actor: str, summary: str, *, severity: str = "info", **payload: Any) -> None:
        """A point-in-time event: a short tracer observation mirrored to JSONL."""
        as_type = _OBSERVATION_TYPES.get(kind, "span")
        with self.tracer.observation(
            f"{kind}:{actor}", as_type=as_type, input=payload, metadata={"severity": severity}
        ) as span:
            span.update(output={"summary": summary})
            self.events.append(
                kind=kind,
                actor=actor,
                summary=summary,
                payload={"severity": severity, **payload},
                trace_id=span.trace_id,
                observation_id=span.id,
            )

    def require_active_observation(self) -> None:
        if self.tracer.current_trace_id() is None:
            raise RuntimeError("Refusing external action with no active observation.")

    def charge_llm(
        self,
        *,
        hold_back_micros: int = 0,
        hold_back_calls: int = 0,
        reservation_floor_micros: int = 0,
        reservation_estimate_micros: int = 0,
        use_headroom: bool = False,
    ) -> int:
        """Admit one LLM call and reserve its estimated cost; returns the reservation.

        Parallel siblings all pass a plain pre-check before any of their costs
        settle, which let one run overshoot its ceiling by 60%. Projecting
        in-flight reservations into the check closes that gap; the caller hands
        the reservation back through add_cost when the real cost lands.
        hold_back_micros lowers this caller's effective ceiling, so ordinary
        nodes cannot spend the slice held back for the final forecast.
        headroom_micros widens only this hard stop, never the advertised
        ceiling, so a run can finish a final pass instead of dying mid-call."""
        self.require_active_observation()
        if self.budget.llm_calls >= self.caps.max_llm_calls - hold_back_calls:
            raise CapExceeded(f"max_llm_calls ({self.caps.max_llm_calls}) reached")
        hard_ceiling = self.caps.max_cost_micros + (self.caps.headroom_micros if use_headroom else 0)
        reservation = max(
            self._call_estimate_micros(),
            reservation_floor_micros,
            reservation_estimate_micros,
        )
        if self.caps.max_cost_micros:
            available = hard_ceiling - hold_back_micros - self.budget.cost_micros - self._in_flight_micros
            if available <= 0 or reservation > available:
                raise CapExceeded(f"max_cost_micros ({self.caps.max_cost_micros}) reached")
        self.budget.llm_calls += 1
        self._in_flight_micros += reservation
        return reservation

    def can_fund_followup_call(
        self, *, hold_back_micros: int = 0, hold_back_calls: int = 0, floor_micros: int = 0
    ) -> bool:
        """True while a node holding the finalisation reserve back could still
        admit one more call; mirrors charge_llm so the gate and a CapExceeded
        coincide. floor_micros guards the cold start before any call settles."""
        if self.budget.llm_calls >= self.caps.max_llm_calls - hold_back_calls:
            return False
        if not self.caps.max_cost_micros:
            return True
        reservation = max(self._call_estimate_micros(), floor_micros)
        available = self.caps.max_cost_micros - hold_back_micros - self.budget.cost_micros - self._in_flight_micros
        return available > 0 and reservation <= available

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

    def add_cost(self, micros: int, *, reservation: int = 0) -> None:
        self.release_reservation(reservation)
        self.budget.cost_micros += micros
        self._settled_cost_micros += micros
        self._settled_calls += 1

    def release_reservation(self, reservation: int) -> None:
        """Return a reservation that will never settle: a failed or cancelled
        call must not hold its estimated cost against the ceiling forever."""
        self._in_flight_micros = max(0, self._in_flight_micros - reservation)

    def _call_estimate_micros(self) -> int:
        if self._settled_calls == 0:
            return _DEFAULT_CALL_ESTIMATE_MICROS
        return self._settled_cost_micros // self._settled_calls

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
