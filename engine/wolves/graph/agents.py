from __future__ import annotations

from functools import cache
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from wolves.agent.deps import AgentDeps
from wolves.agent.tools.market import market_gaps, market_movement
from wolves.agent.tools.memory import (
    forecast_history,
    ledger_query,
    previous_forecast,
    read_journal,
    scenario_update,
    what_changed,
    write_journal,
)
from wolves.agent.tools.meta import read_artifact
from wolves.agent.tools.model import calibration_readback, model_explain
from wolves.agent.tools.retrieval import get_odds, get_results_and_fixtures, rank_relevance, web_fetch, web_search
from wolves.agent.tools.simulation import (
    mixture_spread,
    perturbation_impact,
    run_scenario,
    run_simulation,
    team_path_tree,
)
from wolves.agent.tools.submission import check_forecast, submit_forecast
from wolves.agent.tools.workbench import data_query, run_python, team_dossier
from wolves.graph.contracts import CritiqueOutput, ForecastOutput, GraphPatch, NodeKind, QuantOutput, ResearchOutput
from wolves.prompts import prompt
from wolves.toolkit._truncation import truncate_result
from wolves.toolkit.adapters.pydantic_ai import build_toolset
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

_RESEARCH_FREE_SPECS: list[ToolSpec] = [read_artifact.SPEC]
_POST_CLEAN_CHECK_TOOLS = {"submit_forecast", "write_journal"}
_COPY_REPAIR_TOOLS = {"submit_forecast", "check_forecast"}
_LINEUP_TERMS = ("starting xi", "lineup", "line-up", "teamsheet", "team sheet")
_OFFICIAL_LINEUP_HOSTS = ("fifa.com", "englandfootball.com", "thefa.com")

_NODE_SPECS: dict[NodeKind, list[ToolSpec]] = {
    "research": [
        web_search.SPEC,
        web_fetch.SPEC,
        rank_relevance.SPEC,
        get_odds.SPEC,
        get_results_and_fixtures.SPEC,
        *_RESEARCH_FREE_SPECS,
    ],
    "quant": [
        run_python.SPEC,
        run_simulation.SPEC,
        run_scenario.SPEC,
        data_query.SPEC,
        model_explain.SPEC,
        market_gaps.SPEC,
        market_movement.SPEC,
        team_dossier.SPEC,
        team_path_tree.SPEC,
        ledger_query.SPEC,
        previous_forecast.SPEC,
        forecast_history.SPEC,
        perturbation_impact.SPEC,
        read_artifact.SPEC,
    ],
    "forecast": [
        ledger_query.SPEC,
        run_simulation.SPEC,
        run_scenario.SPEC,
        mixture_spread.SPEC,
        perturbation_impact.SPEC,
        team_path_tree.SPEC,
        model_explain.SPEC,
        team_dossier.SPEC,
        market_gaps.SPEC,
        market_movement.SPEC,
        data_query.SPEC,
        calibration_readback.SPEC,
        previous_forecast.SPEC,
        forecast_history.SPEC,
        what_changed.SPEC,
        scenario_update.SPEC,
        read_journal.SPEC,
        write_journal.SPEC,
        check_forecast.SPEC,
        submit_forecast.SPEC,
        read_artifact.SPEC,
    ],
    "critic": [ledger_query.SPEC, market_gaps.SPEC, run_scenario.SPEC, previous_forecast.SPEC, read_artifact.SPEC],
}

_NODE_OUTPUTS: dict[NodeKind, type] = {
    "research": ResearchOutput,
    "quant": QuantOutput,
    "forecast": ForecastOutput,
    "critic": CritiqueOutput,
}


def _forecast_post_check_refusal(tool_name: str, deps: AgentDeps) -> ToolResult | None:
    if deps.submission.copy_repair_required and tool_name not in _COPY_REPAIR_TOOLS:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="copy_repair_required",
                message=(
                    "The last forecast validation had copy issues only. Fix exactly those words and call "
                    "check_forecast or submit_forecast again; do not call evidence, simulation or planning tools."
                ),
            ),
        )
    if deps.submission.checked_clean is None or tool_name in _POST_CLEAN_CHECK_TOOLS:
        return None
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(
            type="clean_forecast_already_checked",
            message=(
                "A clean check_forecast preview has already passed. Write the journal if still needed, "
                "then call submit_forecast with the checked payload. Do not call more tools."
            ),
        ),
    )


def _host(source_url: str) -> str:
    return urlparse(source_url).netloc.lower().removeprefix("www.")


def _official_lineup_source(source_url: str) -> bool:
    host = _host(source_url)
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in _OFFICIAL_LINEUP_HOSTS)


def _research_source_issues(output: ResearchOutput) -> list[str]:
    issues: list[str] = []
    for index, item in enumerate(output.evidence, start=1):
        text = f"{item.claim} {item.mechanism}".lower()
        if item.status != "confirmed" or not any(term in text for term in _LINEUP_TERMS):
            continue
        if _official_lineup_source(item.source_url):
            continue
        source = _host(item.source_url) or item.source_url
        issues.append(
            f"evidence {index} calls a line-up or starting-XI claim confirmed from {source!r}. "
            "Only official team, federation or FIFA pages may confirm line-ups. Reword it as reported "
            "or predicted with probable/rumour status, or omit it."
        )
    return issues


def _em_dash_paths(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, BaseModel):
        return _em_dash_paths(value.model_dump(mode="json"), path)
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            paths.extend(_em_dash_paths(item, f"{path}.{key}"))
        return paths
    if isinstance(value, list):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_em_dash_paths(item, f"{path}[{index}]"))
        return paths
    if isinstance(value, str) and "\u2014" in value:
        return [path]
    return []


def _reject_em_dashes(value: Any) -> None:
    paths = _em_dash_paths(value)
    if not paths:
        return
    shown = ", ".join(paths[:8])
    extra = "" if len(paths) <= 8 else f" and {len(paths) - 8} more"
    raise ModelRetry(
        f"Replace em dashes with commas, semicolons, parentheses or hyphens in {shown}{extra}."
    )


async def _truncated(spec: ToolSpec, args: Any, ctx: RunContext[AgentDeps], result: ToolResult) -> str:
    return truncate_result(result.model_dump_json(), ctx.deps.settings.tool_result_max_chars)


async def _before_node_tool(spec: ToolSpec, args: Any, ctx: RunContext[AgentDeps]) -> str | None:
    refusal = _forecast_post_check_refusal(spec.name, ctx.deps)
    if refusal is None:
        return None
    ctx.deps.runtime.emit(
        "tool_call",
        ctx.deps.actor,
        f"{spec.name} error: {refusal.error.message[:80] if refusal.error else 'refused'}",
        tool=spec.name,
        ok=False,
    )
    return await _truncated(spec, args, ctx, refusal)


@cache
def node_agent(kind: NodeKind) -> Agent[AgentDeps, Any]:
    """One agent per node kind, built once; model and deps vary per run call."""
    agent: Agent[AgentDeps, Any] = Agent(
        deps_type=AgentDeps,
        output_type=_NODE_OUTPUTS[kind],
        system_prompt=prompt(kind),
        toolsets=[
            build_toolset(
                _NODE_SPECS[kind],
                before_invoke=_before_node_tool if kind == "forecast" else None,
                after_result=_truncated,
            )
        ],
    )

    @agent.output_validator
    def _node_copy_style(output: Any) -> Any:
        _reject_em_dashes(output)
        return output

    if kind == "research":

        @agent.output_validator
        def _research_source_discipline(output: ResearchOutput) -> ResearchOutput:
            issues = _research_source_issues(output)
            if issues:
                raise ModelRetry(" ".join(issues))
            return output

    return agent


@cache
def master_agent(output_retries: int) -> Agent[None, GraphPatch]:
    """The planner: pure structured output over the blackboard summary, no tools."""
    agent: Agent[None, GraphPatch] = Agent(
        output_type=GraphPatch, system_prompt=prompt("master"), output_retries=output_retries
    )

    @agent.output_validator
    def _ops_or_stop(patch: GraphPatch) -> GraphPatch:
        _reject_em_dashes(patch)
        # Opus narrates a wave in reason while emitting ops=[].
        if not patch.ops and not patch.stop:
            raise ModelRetry(
                "Empty patch: put the node ops for the next wave in ops, or set stop=true with your reason. "
                "If you described a wave in reason, emit those ops now."
            )
        return patch

    return agent
