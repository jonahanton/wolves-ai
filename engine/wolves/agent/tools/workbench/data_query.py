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
        "Read-only SQL over the research dataset (DuckDB). Tables: matches (49k internationals "
        "with importance weights), shootouts, market_closes, outright_closes, teams (covariates "
        "incl. squad value), elo_history. Returns at most 200 rows; aggregate in SQL, not in "
        "your head. Free to call."
    ),
    args_model=DataQueryArgs,
    fn=_data_query,
)
