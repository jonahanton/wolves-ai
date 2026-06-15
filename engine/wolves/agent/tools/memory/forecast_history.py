from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ValidationError

from wolves.agent.deps import AgentDeps
from wolves.snapshot import Snapshot, run_day
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class ForecastHistoryArgs(BaseModel):
    team: str
    window: int = 14


def _champion_band(snapshot: Snapshot, team: str) -> tuple[float, float] | None:
    block = snapshot.distributions
    if block is None or 0.1 not in block.quantile_levels or 0.9 not in block.quantile_levels:
        return None
    dist = block.teams.get(team)
    if dist is None or "champion" not in dist.quantiles:
        return None
    quantiles = dist.quantiles["champion"]
    return quantiles[block.quantile_levels.index(0.1)], quantiles[block.quantile_levels.index(0.9)]


def _team_story(snapshot: Snapshot, team: str) -> str | None:
    if snapshot.agent is None:
        return None
    story = snapshot.agent.narrative.team_stories.get(team)
    if story is None:
        return None
    return (story.summary or story.why).strip()[:160] or None


async def _forecast_history(args: ForecastHistoryArgs, deps: AgentDeps) -> ToolResult[Any]:
    if deps.disable_continuity:
        return ToolResult(payload={"team": args.team, "series": []})
    snapshot_dir = deps.settings.runs_root / "snapshots"
    before = date.fromisoformat(deps.as_of) if deps.as_of else None
    series: list[dict[str, Any]] = []
    if snapshot_dir.exists():
        for path in sorted(snapshot_dir.rglob("*.json")):
            if path.name == "latest.json" or path.name.count(".") > 1:
                continue
            try:
                snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
            except ValidationError:
                continue
            if snapshot.run.kind != "agent":
                continue
            if before is not None and date.fromisoformat(run_day(snapshot.run)) >= before:
                continue
            team = next((t for t in snapshot.teams if t.team_id == args.team), None)
            if team is None:
                continue
            point: dict[str, Any] = {
                "run_id": snapshot.run.run_id,
                "created_at": snapshot.run.created_at,
                "as_of": run_day(snapshot.run),
                "kind": snapshot.run.kind,
                "p_title": team.champion_prob,
            }
            band = _champion_band(snapshot, args.team)
            if band is not None:
                point["q10"], point["q90"] = band
            story = _team_story(snapshot, args.team)
            if story is not None:
                point["story"] = story
            series.append(point)
    series.sort(key=lambda p: (p["as_of"], p["created_at"]))
    return ToolResult(payload={"team": args.team, "series": series[-args.window :]})


SPEC = ToolSpec(
    name="forecast_history",
    description=(
        "The published title-probability series for one team across previous agent runs, with the "
        "q10-q90 band where the snapshot carries one and the recorded story where one exists. "
        "Use it to keep today's move, and today's width, coherent with the record. Live and sim-only "
        "republishes are deliberately excluded."
    ),
    args_model=ForecastHistoryArgs,
    fn=_forecast_history,
)
