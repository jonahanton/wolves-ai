from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.scoring import load_previous_snapshots
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult
from wolves.graph.artifacts import MissingRunIndexError, RunArtifactStore
from wolves.s3.artifacts import ArtifactStore
from wolves.snapshot import Snapshot


class PreviousForecastArgs(BaseModel):
    run_id: str | None = None
    on: str | None = None


def _find_snapshot(deps: AgentDeps, args: PreviousForecastArgs) -> Snapshot | None:
    before = date.fromisoformat(args.on) + timedelta(days=1) if args.on else date.fromisoformat(deps.as_of)
    latest, _ = load_previous_snapshots(deps.settings.runs_root / "snapshots", before=before)
    if args.run_id is None:
        return latest
    if latest is not None and latest.run.run_id == args.run_id:
        return latest
    for path in (deps.settings.runs_root / "snapshots").rglob(f"{args.run_id}.json"):
        return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
    return None


async def _previous_forecast(args: PreviousForecastArgs, deps: AgentDeps) -> ToolResult[Any]:
    snapshot = _find_snapshot(deps, args)
    if snapshot is None:
        return ToolResult(
            ok=False, payload=None, error=ToolError(type="not_found", message="no published forecast matches")
        )
    top = sorted(snapshot.teams, key=lambda t: t.champion_prob, reverse=True)[:10]
    payload: dict[str, Any] = {
        "run_id": snapshot.run.run_id,
        "created_at": snapshot.run.created_at,
        "title_probs": {t.team_id: t.champion_prob for t in top},
        "england_reach": snapshot.england.reach_probs if snapshot.england else None,
    }
    if snapshot.agent is not None:
        payload["narrative"] = snapshot.agent.narrative.model_dump(mode="json")
        payload["ledger"] = [e.model_dump(mode="json") for e in snapshot.agent.ledger_entries[:10]]
    try:
        store = RunArtifactStore.open_run(ArtifactStore(deps.settings), snapshot.run.run_id)
        payload["artifacts"] = [r.model_dump(mode="json", exclude={"created_at"}) for r in store.all()]
    except MissingRunIndexError:
        pass
    journal = deps.memory.read_journal(snapshot.run.run_id)
    if journal:
        payload["journal"] = journal[-2000:]
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="previous_forecast",
    description=(
        "A previous run's published forecast: its top title probabilities, narrative, evidence, "
        "artifact index and journal extract. Defaults to the run before today; pass run_id or an "
        "ISO date to reach further back. Open its artifacts with read_artifact via the listed ids "
        "only when that run is today's; older payloads arrive inline here."
    ),
    args_model=PreviousForecastArgs,
    fn=_previous_forecast,
)
