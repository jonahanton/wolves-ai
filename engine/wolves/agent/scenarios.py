from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

ScenarioStatus = Literal["open", "reweighted", "collapsed", "expired"]


class ScenarioEvent(BaseModel):
    scenario_id: str
    name: str
    run_id: str
    status: ScenarioStatus
    weight: float
    reason: str
    at: str


class ScenarioState(BaseModel):
    scenario_id: str
    name: str
    opened_run: str
    status: ScenarioStatus
    weight: float
    history: list[ScenarioEvent]


class UnknownScenarioError(Exception):
    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        super().__init__(f"no scenario {scenario_id!r} in the registry")


class ScenarioRegistry:
    """Cross-run scenario lifecycle as an append-only event log: yesterday's
    open worlds cannot silently vanish, their collapse or survival is part of
    today's argument."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._events: list[ScenarioEvent] = []
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._events.append(ScenarioEvent.model_validate_json(line))

    def open(self, *, name: str, run_id: str, weight: float, reason: str) -> ScenarioState:
        taken = {int(e.scenario_id.removeprefix("scn-")) for e in self._events if e.scenario_id.startswith("scn-")}
        scenario_id = f"scn-{max(taken, default=0) + 1:03d}"
        self._append(
            ScenarioEvent(
                scenario_id=scenario_id,
                name=name,
                run_id=run_id,
                status="open",
                weight=weight,
                reason=reason,
                at=_now(),
            )
        )
        state = self.get(scenario_id)
        assert state is not None
        return state

    def update(
        self, scenario_id: str, *, run_id: str, status: ScenarioStatus, weight: float, reason: str
    ) -> ScenarioState:
        current = self.get(scenario_id)
        if current is None:
            raise UnknownScenarioError(scenario_id)
        self._append(
            ScenarioEvent(
                scenario_id=scenario_id,
                name=current.name,
                run_id=run_id,
                status=status,
                weight=weight,
                reason=reason,
                at=_now(),
            )
        )
        state = self.get(scenario_id)
        assert state is not None
        return state

    def get(self, scenario_id: str) -> ScenarioState | None:
        events = [e for e in self._events if e.scenario_id == scenario_id]
        if not events:
            return None
        latest = events[-1]
        return ScenarioState(
            scenario_id=scenario_id,
            name=latest.name,
            opened_run=events[0].run_id,
            status=latest.status,
            weight=latest.weight,
            history=events,
        )

    def open_scenarios(self) -> list[ScenarioState]:
        states = [self.get(sid) for sid in dict.fromkeys(e.scenario_id for e in self._events)]
        return [s for s in states if s is not None and s.status in ("open", "reweighted")]

    def unresolved_in(self, run_id: str) -> list[ScenarioState]:
        """Open scenarios this run has not yet touched; the soft lifecycle check."""
        return [s for s in self.open_scenarios() if all(e.run_id != run_id for e in s.history)]

    def _append(self, event: ScenarioEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        self._events.append(event)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
