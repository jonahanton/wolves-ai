from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.insights.what_changed import load_latest_snapshot, what_changed
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class WhatChangedArgs(BaseModel):
    move_floor_pp: float = 0.3


async def _what_changed(args: WhatChangedArgs, deps: AgentDeps) -> ToolResult[Any]:
    previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of))
    titles = None
    if deps.forecaster is not None:
        titles = deps.forecaster.title_probs(n_sims=50_000, seed=0)
    diff = what_changed(
        previous=previous,
        current_titles=titles,
        ledger=deps.ledger,
        source_memory=deps.source_memory,
        run_id=deps.runtime.run_id,
        as_of=deps.as_of,
        move_floor_pp=args.move_floor_pp,
    )
    return ToolResult(payload=diff.model_dump(mode="json"))


SPEC = ToolSpec(
    name="what_changed",
    description=(
        "The input diff since the previous published run: baseline title moves beyond the floor, "
        "sources never seen before this run and evidence that expired in between."
    ),
    args_model=WhatChangedArgs,
    fn=_what_changed,
)
