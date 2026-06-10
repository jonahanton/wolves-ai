from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.snapshot import Snapshot


class ForecastHistoryArgs(BaseModel):
    team: str
    window: int = 14


async def _forecast_history(args: ForecastHistoryArgs, deps: AgentDeps) -> ToolResult[Any]:
    snapshot_dir = deps.settings.runs_root / "snapshots"
    series: list[dict[str, Any]] = []
    if snapshot_dir.exists():
        for path in sorted(snapshot_dir.rglob("*.json")):
            if path.name == "latest.json":
                continue
            try:
                snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
            except ValidationError:
                continue
            team = next((t for t in snapshot.teams if t.team_id == args.team), None)
            if team is None:
                continue
            point: dict[str, Any] = {
                "run_id": snapshot.run.run_id,
                "created_at": snapshot.run.created_at,
                "kind": snapshot.run.kind,
                "p_title": team.champion_prob,
            }
            if snapshot.agent is not None and snapshot.agent.narrative.england_story and args.team == "england":
                point["story"] = snapshot.agent.narrative.england_story[:160]
            series.append(point)
    series.sort(key=lambda p: p["created_at"])
    return ToolResult(payload={"team": args.team, "series": series[-args.window :]})


SPEC = ToolSpec(
    name="forecast_history",
    description=(
        "The published title-probability series for one team across recent runs, with the "
        "recorded story where one exists. Use it to keep today's move coherent with the record."
    ),
    args_model=ForecastHistoryArgs,
    fn=_forecast_history,
)
