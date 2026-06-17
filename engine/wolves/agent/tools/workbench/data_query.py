from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.data.query import DatasetQuery
from wolves.data.store import DatasetStore
from wolves.models.contracts import DatasetHandle
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

_MAX_ROWS = 200


class DataQueryArgs(BaseModel):
    sql: str


async def _data_query(args: DataQueryArgs, deps: AgentDeps) -> ToolResult[Any]:
    try:
        path, manifest = DatasetStore(deps.settings).fetch()
    except Exception as exc:
        return ToolResult(
            ok=False, payload=None, error=ToolError(type="no_dataset", message=f"dataset unavailable: {exc}")
        )
    handle = DatasetHandle(path=path, dataset_id=manifest.dataset_id)
    with DatasetQuery(handle) as query:
        try:
            rows = query.sql(args.sql)
        except Exception as exc:
            return ToolResult(ok=False, payload=None, error=ToolError(type="query_failed", message=str(exc)))
    return ToolResult(payload={"rows": rows[:_MAX_ROWS], "row_count": len(rows), "truncated": len(rows) > _MAX_ROWS})


SPEC = ToolSpec(
    name="data_query",
    description=(
        "Read-only SQL over the historical research dataset (DuckDB), not the current 2026 "
        "tournament schedule. Tables: matches (49k internationals with importance weights; "
        "columns include date, home_team, away_team, home_goals, away_goals, tournament), "
        "shootouts, market_closes, outright_closes, teams (covariates incl. squad value), "
        "elo_history, plus any extra tables shown by SHOW TABLES. For current tournament fixtures, "
        "groups, slots or played results, use team_dossier, team_path_tree, run_simulation, or "
        "wq.fixtures inside run_python. Returns at most 200 rows; aggregate in SQL, not in your head. "
        "Free to call."
    ),
    args_model=DataQueryArgs,
    fn=_data_query,
)
