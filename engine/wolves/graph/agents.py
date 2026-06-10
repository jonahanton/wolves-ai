from __future__ import annotations

from functools import cache
from typing import Any

from pydantic_ai import Agent, RunContext

from wolves.agent.deps import AgentDeps
from wolves.agent.tools import (
    calibration_readback,
    data_query,
    forecast_history,
    get_odds,
    get_results_and_fixtures,
    ledger_query,
    market_movement,
    model_explain,
    model_vs_market,
    perturbation_impact,
    previous_forecast,
    rank_relevance,
    read_artifact,
    read_journal,
    run_python,
    run_scenario,
    run_simulation,
    scenario_update,
    submit_forecast,
    team_dossier,
    team_path_tree,
    think,
    todo,
    web_fetch,
    web_search,
    what_changed,
    write_journal,
)
from wolves.agent_tools.adapters.pydantic_ai import build_toolset
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.graph.contracts import CritiqueOutput, ForecastOutput, GraphPatch, NodeKind, QuantOutput, ResearchOutput
from wolves.prompts import prompt
from wolves.tools._truncation import truncate_result

_FREE_SPECS: list[ToolSpec] = [think.SPEC, todo.SPEC, read_artifact.SPEC]

_NODE_SPECS: dict[NodeKind, list[ToolSpec]] = {
    "research": [
        web_search.SPEC,
        web_fetch.SPEC,
        rank_relevance.SPEC,
        get_odds.SPEC,
        get_results_and_fixtures.SPEC,
        *_FREE_SPECS,
    ],
    "quant": [
        run_python.SPEC,
        run_simulation.SPEC,
        data_query.SPEC,
        model_explain.SPEC,
        model_vs_market.SPEC,
        perturbation_impact.SPEC,
        *_FREE_SPECS,
    ],
    "forecast": [
        ledger_query.SPEC,
        run_simulation.SPEC,
        run_scenario.SPEC,
        perturbation_impact.SPEC,
        team_path_tree.SPEC,
        model_explain.SPEC,
        team_dossier.SPEC,
        model_vs_market.SPEC,
        market_movement.SPEC,
        data_query.SPEC,
        calibration_readback.SPEC,
        previous_forecast.SPEC,
        forecast_history.SPEC,
        what_changed.SPEC,
        scenario_update.SPEC,
        read_journal.SPEC,
        write_journal.SPEC,
        submit_forecast.SPEC,
        *_FREE_SPECS,
    ],
    "critic": [ledger_query.SPEC, model_vs_market.SPEC, run_scenario.SPEC, previous_forecast.SPEC, *_FREE_SPECS],
}

_NODE_OUTPUTS: dict[NodeKind, type] = {
    "research": ResearchOutput,
    "quant": QuantOutput,
    "forecast": ForecastOutput,
    "critic": CritiqueOutput,
}


async def _truncated(spec: ToolSpec, args: Any, ctx: RunContext[AgentDeps], result: ToolResult) -> str:
    return truncate_result(result.model_dump_json(), ctx.deps.settings.tool_result_max_chars)


@cache
def node_agent(kind: NodeKind) -> Agent[AgentDeps, Any]:
    """One agent per node kind, built once; model and deps vary per run call."""
    return Agent(
        deps_type=AgentDeps,
        output_type=_NODE_OUTPUTS[kind],
        system_prompt=prompt(kind),
        toolsets=[build_toolset(_NODE_SPECS[kind], after_result=_truncated)],
    )


@cache
def master_agent() -> Agent[None, GraphPatch]:
    """The planner: pure structured output over the blackboard summary, no tools."""
    return Agent(output_type=GraphPatch, system_prompt=prompt("master"))
