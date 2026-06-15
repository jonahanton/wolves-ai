from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.continuity import build_previous_run_digest
from wolves.agent.deps import AgentDeps
from wolves.snapshot import Snapshot, run_day
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


class PreviousForecastArgs(BaseModel):
    run_id: str | None = None
    on: str | None = None
    kind: Literal["agent"] | None = "agent"


def _recent_runs(deps: AgentDeps, *, before: date, limit: int = 10) -> list[dict[str, str]]:
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
        if snapshot.run.kind == "agent" and date.fromisoformat(run_day(snapshot.run)) < before:
            runs.append(
                {
                    "run_id": snapshot.run.run_id,
                    "created_at": snapshot.run.created_at,
                    "as_of": run_day(snapshot.run),
                    "kind": snapshot.run.kind,
                }
            )
    return sorted(runs, key=_run_sort_key, reverse=True)[:limit]


def _run_sort_key(run: dict[str, str]) -> tuple[date, str]:
    return date.fromisoformat(run["as_of"]), run["created_at"]


def _compact_world(world: Any) -> dict[str, Any]:
    payload = world.model_dump(mode="json")
    return {
        "name": payload["name"],
        "weight": payload["weight"],
        "perturbations": payload.get("perturbations", []),
        "latent_effects": payload.get("latent_effects", []),
        "title_probs": payload.get("title_probs", {}),
    }


def _before_boundary(deps: AgentDeps, args: PreviousForecastArgs) -> date:
    as_of_boundary = date.fromisoformat(deps.as_of)
    requested = date.fromisoformat(args.on) + timedelta(days=1) if args.on else as_of_boundary
    return min(requested, as_of_boundary)


def _find_snapshot(deps: AgentDeps, args: PreviousForecastArgs) -> Snapshot | None:
    before = _before_boundary(deps, args)
    snapshot_dir = deps.settings.runs_root / "snapshots"

    from wolves.agent.scoring import latest_snapshot_by_kind

    latest = latest_snapshot_by_kind(snapshot_dir, before=before, kind="agent")
    if args.run_id is None:
        return latest
    if latest is not None and latest.run.run_id == args.run_id:
        return latest
    for path in snapshot_dir.rglob(f"{args.run_id}.json"):
        snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        if snapshot.run.kind == "agent" and date.fromisoformat(run_day(snapshot.run)) < before:
            return snapshot
    return None


def _non_agent_run_id(run_id: str | None) -> bool:
    return run_id is not None and not run_id.startswith("agent-")


async def _previous_forecast(args: PreviousForecastArgs, deps: AgentDeps) -> ToolResult[Any]:
    if deps.disable_continuity:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="not_found",
                message="previous forecast continuity is disabled for this scratch run",
            ),
        )
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
        "recent_runs": _recent_runs(deps, before=_before_boundary(deps, args)),
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
        payload["market_gaps"] = [g.model_dump(mode="json") for g in snapshot.agent.market_gaps]
        payload["news_impacts"] = snapshot.agent.news_impacts
        payload["copy_guard_version"] = snapshot.agent.copy_guard_version
        payload["branch_audit"] = snapshot.agent.branch_audit
        payload["world_metadata"] = snapshot.agent.world_metadata
    from wolves.graph.artifacts import MissingRunIndexError, RunArtifactStore
    from wolves.s3.artifacts import ArtifactStore

    store: RunArtifactStore | None = None
    try:
        store = RunArtifactStore.open_run(ArtifactStore(deps.settings), snapshot.run.run_id)
        payload["artifact_index_available"] = True
        payload["artifacts"] = [r.model_dump(mode="json", exclude={"created_at"}) for r in store.all()]
    except MissingRunIndexError:
        payload["warnings"].append(f"artifact index missing for {snapshot.run.run_id}")
    if snapshot.agent is not None and snapshot.agent.copy_guard_version is None:
        payload["warnings"].append(
            f"copy guard version missing for {snapshot.run.run_id}; treat public narrative claims as weaker "
            "than ledger, artifact and published distribution data"
        )
    digest = build_previous_run_digest(snapshot, settings=deps.settings, store=store)
    payload["continuity_digest"] = digest.model_dump(mode="json")
    payload["continuity_summary"] = digest.master_summary()
    for warning in digest.warnings:
        if warning not in payload["warnings"]:
            payload["warnings"].append(warning)
    journal = deps.memory.read_journal(snapshot.run.run_id)
    if journal:
        payload["journal"] = journal[-2000:]
    else:
        warning = f"journal missing for {snapshot.run.run_id}"
        if warning not in payload["warnings"]:
            payload["warnings"].append(warning)
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="previous_forecast",
    description=(
        "A previous agent run's published forecast: its top title probabilities, narrative, evidence, "
        "artifact index, continuity_digest, journal extract and an index of recent runs with exact timestamps. "
        "The published_distribution block is the compact source of truth for prior worlds, "
        "scenario weights and camps; use it directly when artifact_index_available is false, "
        "and never reconstruct prior worlds from prose. "
        "continuity_digest summarises the previous run's process, failed nodes, validator repairs, source trail "
        "and accepted artifacts; use it as an audit trail, not a template. "
        "This tool never opens live or sim-only snapshots: they are not continuity anchors. For current "
        "results, standings, fixtures or market state use get_results_and_fixtures, what_changed, "
        "market_gaps or the workbench. Pass an agent run_id or an ISO date for any older agent run. "
        "Open a listed artifact with read_artifact(artifact_id, run_id=...), including past quant "
        "workspaces file by file."
    ),
    args_model=PreviousForecastArgs,
    fn=_previous_forecast,
)
