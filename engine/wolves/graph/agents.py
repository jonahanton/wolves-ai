from __future__ import annotations

from functools import cache
from typing import Any

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
from wolves.agent.tools.meta import read_artifact, think, todo
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
from wolves.toolkit.result import ToolResult

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
        *_FREE_SPECS,
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
        *_FREE_SPECS,
    ],
    "critic": [ledger_query.SPEC, market_gaps.SPEC, run_scenario.SPEC, previous_forecast.SPEC, *_FREE_SPECS],
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
def master_agent(output_retries: int) -> Agent[None, GraphPatch]:
    """The planner: pure structured output over the blackboard summary, no tools."""
    agent: Agent[None, GraphPatch] = Agent(
        output_type=GraphPatch, system_prompt=prompt("master"), output_retries=output_retries
    )

    @agent.output_validator
    def _ops_or_stop(patch: GraphPatch) -> GraphPatch:
        # Opus narrates a wave in reason while emitting ops=[].
        if not patch.ops and not patch.stop:
            raise ModelRetry(
                "Empty patch: put the node ops for the next wave in ops, or set stop=true with your reason. "
                "If you described a wave in reason, emit those ops now."
            )
        return patch

    return agent
