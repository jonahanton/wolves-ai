from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import forecaster_or_refuse, reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.insights.dossier import team_dossier


class TeamDossierArgs(BaseModel):
    team: str


async def _team_dossier(args: TeamDossierArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps) or forecaster_or_refuse(deps)
    if refused is not None:
        return refused
    assert deps.forecaster is not None
    dossier = team_dossier(deps.forecaster, args.team, archive_dir=deps.settings.runs_root / "odds-archive")
    return ToolResult(payload=dossier.model_dump(mode="json"))


SPEC = ToolSpec(
    name="team_dossier",
    description=(
        "Everything about one team in a single call: upcoming fixtures, model reach, current and "
        "historical market prices, the strength explanation and recent form."
    ),
    args_model=TeamDossierArgs,
    fn=_team_dossier,
)
