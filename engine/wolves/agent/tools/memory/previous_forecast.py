from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.snapshot import Snapshot
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


class PreviousForecastArgs(BaseModel):
    run_id: str | None = None
    on: str | None = None
    kind: Literal["agent"] | None = "agent"


def _recent_runs(deps: AgentDeps, limit: int = 10) -> list[dict[str, str]]:
    runs: list[dict[str, str]] = []
    snapshot_dir = deps.settings.runs_root / "snapshots"
    if not snapshot_dir.exists():
        return runs
    for path in snapshot_dir.rglob("*.json"):
        if path.name == "latest.json" or path.name.count(".") > 1:
            continue
        try:
            snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if snapshot.run.kind == "agent":
            runs.append(
                {"run_id": snapshot.run.run_id, "created_at": snapshot.run.created_at, "kind": snapshot.run.kind}
            )
    return sorted(runs, key=lambda r: r["created_at"], reverse=True)[:limit]


def _compact_world(world: Any) -> dict[str, Any]:
    payload = world.model_dump(mode="json")
    return {
        "name": payload["name"],
        "weight": payload["weight"],
        "perturbations": payload.get("perturbations", []),
        "latent_effects": payload.get("latent_effects", []),
        "title_probs": payload.get("title_probs", {}),
    }


def _find_snapshot(deps: AgentDeps, args: PreviousForecastArgs) -> Snapshot | None:
    before = date.fromisoformat(args.on) + timedelta(days=1) if args.on else date.fromisoformat(deps.as_of)
    snapshot_dir = deps.settings.runs_root / "snapshots"

    from wolves.agent.scoring import latest_snapshot_by_kind

    latest = latest_snapshot_by_kind(snapshot_dir, before=before, kind="agent")
    if args.run_id is None:
        return latest
    if latest is not None and latest.run.run_id == args.run_id:
        return latest
    for path in snapshot_dir.rglob(f"{args.run_id}.json"):
        return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
    return None


def _non_agent_run_id(run_id: str | None) -> bool:
    return run_id is not None and not run_id.startswith("agent-")


async def _previous_forecast(args: PreviousForecastArgs, deps: AgentDeps) -> ToolResult[Any]:
    if _non_agent_run_id(args.run_id):
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="invalid_arguments",
                message=(
                    "previous_forecast only opens agent forecasts. For live results, standings, fixtures or "
                    "markets use get_results_and_fixtures, what_changed, market_gaps or the workbench."
                ),
            ),
        )
    snapshot = _find_snapshot(deps, args)
    if snapshot is None:
        return ToolResult(
            ok=False, payload=None, error=ToolError(type="not_found", message="no published forecast matches")
        )
    if snapshot.run.kind != "agent":
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(type="invalid_arguments", message=f"run {snapshot.run.run_id} is not an agent forecast"),
        )
    top = sorted(snapshot.teams, key=lambda t: t.champion_prob, reverse=True)[:10]
    payload: dict[str, Any] = {
        "run_id": snapshot.run.run_id,
        "kind": snapshot.run.kind,
        "created_at": snapshot.run.created_at,
        "title_probs": {t.team_id: t.champion_prob for t in top},
        "focus_reach": snapshot.focus.reach_probs if snapshot.focus else None,
        "recent_runs": _recent_runs(deps),
        "artifact_index_available": False,
        "warnings": [],
    }
    if snapshot.agent is not None:
        payload["artifact_id"] = snapshot.agent.artifact_id
        scenario_weights = [w.model_dump(mode="json") for w in snapshot.agent.scenario_weights]
        camps = [c.model_dump(mode="json") for c in snapshot.agent.camps]
        worlds = [_compact_world(w) for w in snapshot.agent.worlds]
        payload["published_distribution"] = {
            "artifact_id": snapshot.agent.artifact_id,
            "scenario_weights": scenario_weights,
            "camps": camps,
            "worlds": worlds,
        }
        payload["scenario_weights"] = scenario_weights
        payload["camps"] = camps
        payload["worlds"] = worlds
        payload["quant_findings"] = [q.model_dump(mode="json") for q in snapshot.agent.quant_findings]
        payload["narrative"] = snapshot.agent.narrative.model_dump(mode="json")
        payload["ledger"] = [e.model_dump(mode="json") for e in snapshot.agent.ledger_entries]
    from wolves.graph.artifacts import MissingRunIndexError, RunArtifactStore
    from wolves.s3.artifacts import ArtifactStore

    try:
        store = RunArtifactStore.open_run(ArtifactStore(deps.settings), snapshot.run.run_id)
        payload["artifact_index_available"] = True
        payload["artifacts"] = [r.model_dump(mode="json", exclude={"created_at"}) for r in store.all()]
    except MissingRunIndexError:
        payload["warnings"].append(f"artifact index missing for {snapshot.run.run_id}")
    journal = deps.memory.read_journal(snapshot.run.run_id)
    if journal:
        payload["journal"] = journal[-2000:]
    else:
        payload["warnings"].append(f"journal missing for {snapshot.run.run_id}")
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="previous_forecast",
    description=(
        "A previous agent run's published forecast: its top title probabilities, narrative, evidence, "
        "artifact index, journal extract and an index of recent runs with exact timestamps. "
        "The published_distribution block is the compact source of truth for prior worlds, "
        "scenario weights and camps; use it directly when artifact_index_available is false, "
        "and never reconstruct prior worlds from prose. "
        "This tool never opens live or sim-only snapshots: they are not continuity anchors. For current "
        "results, standings, fixtures or market state use get_results_and_fixtures, what_changed, "
        "market_gaps or the workbench. Pass an agent run_id or an ISO date for any older agent run. "
        "Open a listed artifact with read_artifact(artifact_id, run_id=...), including past quant "
        "workspaces file by file."
    ),
    args_model=PreviousForecastArgs,
    fn=_previous_forecast,
)
