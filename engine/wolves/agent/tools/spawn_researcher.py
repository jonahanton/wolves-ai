from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.contracts import ResearchBrief, WorkerResult
from wolves.agent.deps import AgentDeps
from wolves.agent.researcher import run_researcher
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class SpawnResearcherArgs(BaseModel):
    briefs: list[ResearchBrief] = Field(min_length=1)


async def _spawn_researcher(args: SpawnResearcherArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    timeout = deps.settings.researcher_timeout_seconds

    async def run_one(index: int, brief: ResearchBrief) -> WorkerResult:
        worker_id = f"{deps.actor}-researcher-{index + 1}"
        try:
            return await asyncio.wait_for(run_researcher(deps, brief, worker_id=worker_id), timeout=timeout)
        except TimeoutError:
            return WorkerResult(
                objective=brief.objective,
                summary=f"Worker timed out after {timeout:.0f}s.",
                signals=["timeout: findings missing, consider a narrower brief"],
            )

    results = await asyncio.gather(*(run_one(i, brief) for i, brief in enumerate(args.briefs)))
    deps.runtime.emit(
        "research",
        deps.actor,
        f"{len(results)} researcher(s) returned",
        objectives=[r.objective for r in results],
        signals=[s for r in results for s in r.signals],
    )
    return ToolResult(payload={"results": [r.model_dump() for r in results]})


SPEC = ToolSpec(
    name="spawn_researcher",
    description=(
        "Delegate focused research to one or more parallel sub-researchers. You are briefing a capable "
        "specialist who cannot see your reasoning: a good brief states the specific sub-question, the relevant "
        "context (cite ledger entry ids in input_artifact_ids), exactly what to produce, what to avoid, and "
        "what done-well looks like. Workers return evidence items and signals you must address or explicitly "
        "ignore. Delegation is your choice, never a required step."
    ),
    args_model=SpawnResearcherArgs,
    fn=_spawn_researcher,
)
