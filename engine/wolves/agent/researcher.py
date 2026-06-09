from __future__ import annotations

import dataclasses
from pathlib import Path

from wolves.agent._dispatch import dispatch_tool_uses
from wolves.agent.contracts import ResearchBrief, WorkerResult
from wolves.agent.deps import AgentDeps
from wolves.agent.tools import report_findings, web_fetch, web_search
from wolves.agent_tools.adapters.anthropic import to_anthropic_tools
from wolves.tools._budget_gate import BudgetGate

_PROMPT = (Path(__file__).parent / "prompts" / "researcher.md").read_text(encoding="utf-8")


def researcher_toolset() -> list:
    return [web_search.SPEC, web_fetch.SPEC, report_findings.SPEC]


def _kickoff(brief: ResearchBrief, deps: AgentDeps) -> str:
    parts = [f"Objective: {brief.objective}", "", f"Brief: {brief.brief}"]
    artefacts = [deps.ledger.get(entry_id) for entry_id in brief.input_artifact_ids]
    known = [a for a in artefacts if a is not None]
    if known:
        parts.append("")
        parts.append("Context artefacts from the ledger:")
        parts.extend(f"- {a.id} [{a.status}] {a.claim} ({a.source_url})" for a in known)
    return "\n".join(parts)


async def run_researcher(master_deps: AgentDeps, brief: ResearchBrief, *, worker_id: str) -> WorkerResult:
    """Run one sub-researcher loop: shared runtime, restricted toolset, own gate."""
    deps = dataclasses.replace(
        master_deps,
        actor=worker_id,
        gate=BudgetGate(master_deps.settings.researcher_tool_budget),
        worker_reports=[],
        python_calls=0,
    )
    specs = researcher_toolset()
    tools = to_anthropic_tools(specs)
    messages: list[dict] = [{"role": "user", "content": _kickoff(brief, deps)}]

    for _ in range(deps.settings.researcher_max_turns):
        turn = await deps.llm.tool_turn(
            actor=worker_id,
            prompt_name="researcher_loop",
            messages=messages,
            tools=tools,
            system=_PROMPT,
            max_tokens=2000,
        )
        messages.append({"role": "assistant", "content": turn.content})
        if not turn.tool_use_blocks:
            messages.append({"role": "user", "content": "Finish by calling report_findings with what you have."})
            continue
        results = await dispatch_tool_uses(turn, specs, deps)
        messages.append({"role": "user", "content": results})
        if deps.worker_reports:
            return deps.worker_reports[-1]

    return WorkerResult(
        objective=brief.objective,
        summary="Worker exhausted its turn budget before reporting.",
        signals=["turns_exhausted: findings may be incomplete"],
    )
