from __future__ import annotations

import re
import unicodedata
from functools import cache
from typing import Any
from urllib.parse import urlparse

from pydantic_ai import Agent, ModelRetry, RunContext

from wolves.agent.deps import AgentDeps
from wolves.agent.sources import official_body_source
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
from wolves.sim.format import Team, load_format
from wolves.toolkit._truncation import truncate_result
from wolves.toolkit.adapters.pydantic_ai import build_toolset
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

_RESEARCH_FREE_SPECS: list[ToolSpec] = [read_artifact.SPEC]
_POST_CLEAN_CHECK_TOOLS = {"submit_forecast", "write_journal"}
_COPY_REPAIR_TOOLS = {"submit_forecast", "check_forecast"}
_LINEUP_TERMS = ("starting xi", "lineup", "line-up", "teamsheet", "team sheet")
_FAKE_TOOL_HOSTS = {"get_odds", "get_results_and_fixtures"}
_INTERNAL_SOURCE_URLS = {"internal://get_odds", "internal://get_results_and_fixtures"}
_PLACEHOLDER_HOSTS = {"example.com", "example.org", "example.net"}
_GROUP_MENTION = re.compile(r"\bgroup\s+([A-L])\b", re.IGNORECASE)
_GROUP_CONTEXT = re.compile(r"\(group\s+([A-L])\)", re.IGNORECASE)
_SCORELINE = re.compile(r"\b\d+\s*[-:]\s*\d+\b")
_MAX_REASONABLE_STRENGTH_DELTA = 0.5

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

# The critic slot loads the pre-mortem prompt; dispatch maps stay keyed on kind.
_PROMPT_NAME: dict[NodeKind, str] = {"critic": "premortem"}


def _forecast_post_check_refusal(tool_name: str, deps: AgentDeps) -> ToolResult | None:
    if deps.submission.copy_repair_blocked:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="copy_repair_loop",
                message=(
                    "The same copy-only validation issues repeated. Stop calling tools and return a short "
                    "ForecastOutput summary so the master can replan finalisation."
                ),
            ),
        )
    if deps.submission.referee_replan_required:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="referee_replan_required",
                message=(
                    "The final referee asked for master replanning. Stop calling tools and return a short "
                    "ForecastOutput summary so the master can open the next research or quant wave."
                ),
            ),
        )
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
    if deps.submission.publication_blocked and not deps.submission.copy_repair_required:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="publication_blocked",
                message=(
                    "Publication is blocked by the final referee. Stop calling tools and return a short "
                    "ForecastOutput summary so the master can replan or the run can fail for audit."
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
    return official_body_source(source_url)


def _fake_tool_source(source_url: str) -> bool:
    return _host(source_url) in _FAKE_TOOL_HOSTS


def _fetched_public_source(source_url: str, deps: AgentDeps | None) -> bool:
    if deps is None or deps.source_memory is None:
        return True
    seen = deps.source_memory.seen(source_url)
    return seen is not None and seen.last_seen_run == deps.runtime.run_id and seen.disposition == "fetched"


def _source_label(source_url: str) -> str:
    host = _host(source_url)
    return host or source_url


def _team_groups(deps: AgentDeps) -> dict[str, str]:
    try:
        return {team.id: team.group for team in load_format(deps.settings.data_dir).teams}
    except (OSError, ValueError):
        return {}


def _teams(deps: AgentDeps) -> list[Team]:
    try:
        return load_format(deps.settings.data_dir).teams
    except (OSError, ValueError):
        return []


def _normalise_team_key(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold().replace("&", "and"))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


def _team_keys(team: Team) -> set[str]:
    keys = {_normalise_team_key(team.name), _normalise_team_key(team.id.replace("-", " "))}
    return {key for key in keys if key}


def _last_mentioned_team(text: str, teams: list[Team]) -> Team | None:
    haystack = f" {_normalise_team_key(text)} "
    seen: list[tuple[int, Team]] = []
    for team in teams:
        positions = [haystack.rfind(f" {key} ") for key in _team_keys(team)]
        position = max(positions, default=-1)
        if position >= 0:
            seen.append((position, team))
    if not seen:
        return None
    return max(seen, key=lambda item: item[0])[1]


def _first_mentioned_team(text: str, teams: list[Team]) -> Team | None:
    haystack = f" {_normalise_team_key(text)} "
    seen: list[tuple[int, Team]] = []
    for team in teams:
        positions = [haystack.find(f" {key} ") for key in _team_keys(team)]
        position = min((p for p in positions if p >= 0), default=-1)
        if position >= 0:
            seen.append((position, team))
    if not seen:
        return None
    return min(seen, key=lambda item: item[0])[1]


def _fixture_clause_teams(text: str, teams: list[Team]) -> list[Team]:
    found: list[Team] = []
    for scoreline in _SCORELINE.finditer(text):
        home = _last_mentioned_team(text[: scoreline.start()], teams)
        away = _first_mentioned_team(text[scoreline.end() :], teams)
        for team in (home, away):
            if team is not None and team not in found:
                found.append(team)
    return found


def _group_context_window(text: str, end: int) -> str:
    start = max(
        text.rfind(".", 0, end),
        text.rfind(";", 0, end),
        text.rfind("\n", 0, end),
        text.rfind(",", 0, end),
    )
    return text[start + 1 : end]


def _research_group_context_issues(output: ResearchOutput, deps: AgentDeps | None) -> list[str]:
    if deps is None:
        return []
    teams = _teams(deps)
    if not teams:
        return []
    issues: list[str] = []
    texts = [
        ("summary", output.summary),
        *((f"signal {index}", signal) for index, signal in enumerate(output.signals, 1)),
    ]
    for label, text in texts:
        for mention in _GROUP_CONTEXT.finditer(text):
            group = mention.group(1).upper()
            teams_in_context = _fixture_clause_teams(_group_context_window(text, mention.start()), teams)
            wrong = [team for team in teams_in_context if team.group != group]
            if wrong:
                expected = ", ".join(f"{team.id} is group {team.group}" for team in wrong[:4])
                issues.append(f"{label} assigns {expected} to group {group}; use the canonical tournament groups.")
    return issues


def _research_source_issues(output: ResearchOutput, deps: AgentDeps | None = None) -> list[str]:
    issues: list[str] = []
    groups = _team_groups(deps) if deps is not None else {}
    for index, item in enumerate(output.evidence, start=1):
        source_url = item.source_url.strip()
        internal_source = source_url in _INTERNAL_SOURCE_URLS
        if not source_url.startswith(("http://", "https://")) and not internal_source:
            issues.append(
                f"evidence {index} uses non-canonical internal source {source_url!r}. "
                "Use internal://get_odds, internal://get_results_and_fixtures, or a fetched public URL."
            )
        if not internal_source and _host(source_url) in _PLACEHOLDER_HOSTS:
            issues.append(f"evidence {index} cites placeholder URL {source_url!r}; cite the real source.")
        if not internal_source and _fake_tool_source(item.source_url):
            issues.append(
                f"evidence {index} cites first-party tool output as fake web URL {item.source_url!r}. "
                "Use source_url 'internal://get_odds' or 'internal://get_results_and_fixtures', "
                "or cite a fetched public URL."
            )
        if source_url.startswith(("http://", "https://")) and not _fetched_public_source(source_url, deps):
            issues.append(
                f"evidence {index} cites public URL {source_url!r} without fetching or cached-fetching it this run. "
                "Fetch the page first, or move the finding to signals if it is only search-snippet context."
            )
        if abs(item.proposed_delta) > _MAX_REASONABLE_STRENGTH_DELTA:
            issues.append(
                f"evidence {index} proposed_delta {item.proposed_delta:g} is not in model-strength units. "
                "Use strength units where 0.1 is roughly 100 Elo, or leave it at 0."
            )
        if item.team_id and item.team_id in groups:
            text_for_group = " ".join([item.claim, item.quote, item.mechanism])
            mentioned = {match.upper() for match in _GROUP_MENTION.findall(text_for_group)}
            wrong = sorted(group for group in mentioned if group != groups[item.team_id])
            if wrong:
                issues.append(
                    f"evidence {index} assigns {item.team_id} to group {', '.join(wrong)}, "
                    f"but the tournament format has group {groups[item.team_id]}."
                )
        text = f"{item.claim} {item.mechanism}".lower()
        if item.status != "confirmed" or not any(term in text for term in _LINEUP_TERMS):
            continue
        if _official_lineup_source(item.source_url):
            continue
        source = _source_label(item.source_url)
        issues.append(
            f"evidence {index} calls a line-up or starting-XI claim confirmed from {source!r}. "
            "Only official team, federation or FIFA pages may confirm line-ups. Reword it as reported "
            "or predicted with probable/rumour status, or omit it."
        )
    for branch_index, branch in enumerate(output.candidate_branches, start=1):
        invalid = [index for index in branch.evidence_indices if index < 1 or index > len(output.evidence)]
        if invalid:
            issues.append(
                f"candidate_branches {branch_index} references unknown evidence_indices "
                f"{', '.join(str(index) for index in invalid)}."
            )
        if branch.confidence in {"medium", "high"} and not branch.source_ids and not branch.evidence_indices:
            issues.append(
                f"candidate_branches {branch_index} has {branch.confidence} confidence but no source_ids or "
                "evidence_indices; attach the receipts that make it worth quant pricing."
            )
    issues.extend(_research_group_context_issues(output, deps))
    return issues


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
        system_prompt=prompt(_PROMPT_NAME.get(kind, kind)),
        output_retries=2 if kind == "research" else 1,
        toolsets=[
            build_toolset(
                _NODE_SPECS[kind],
                before_invoke=_before_node_tool if kind == "forecast" else None,
                after_result=_truncated,
            )
        ],
    )

    if kind == "research":

        @agent.output_validator
        def _research_source_discipline(ctx: RunContext[AgentDeps], output: ResearchOutput) -> ResearchOutput:
            _demote_unfetchable_snippets(output, ctx.deps)
            issues = _research_source_issues(output, ctx.deps)
            if issues:
                ctx.deps.runtime.emit(
                    "output_retry",
                    ctx.deps.actor,
                    f"research output rejected: {issues[0][:120]}",
                    issues=issues,
                )
                raise ModelRetry(" ".join(issues))
            return output

    return agent


def _demote_unfetchable_snippets(output: ResearchOutput, deps: AgentDeps) -> None:
    """When the tool budget is spent, an evidence item citing a public URL the
    run could not fetch is downgraded to a signal rather than failing the whole
    node. Budget that remained means the model chose not to fetch, so the hard
    reject stands. Branch-referenced findings are load-bearing and never moved."""
    if not deps.gate.exhausted:
        return
    referenced = {index for branch in output.candidate_branches for index in branch.evidence_indices}
    keep: list[Any] = []
    remap: dict[int, int] = {}
    for index, item in enumerate(output.evidence, start=1):
        url = item.source_url.strip()
        demotable = (
            url.startswith(("http://", "https://"))
            and url not in _INTERNAL_SOURCE_URLS
            and _host(url) not in _PLACEHOLDER_HOSTS
            and not _fake_tool_source(url)
            and not _fetched_public_source(url, deps)
            and index not in referenced
        )
        if demotable:
            output.signals.append(f"unverified ({_source_label(url)}): {item.claim}")
            deps.runtime.emit(
                "evidence_demoted",
                deps.actor,
                f"unfetched snippet demoted to signal, budget spent: {url[:80]}",
            )
            continue
        remap[index] = len(keep) + 1
        keep.append(item)
    if len(keep) == len(output.evidence):
        return
    output.evidence = keep
    for branch in output.candidate_branches:
        branch.evidence_indices = [remap[index] for index in branch.evidence_indices if index in remap]


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
