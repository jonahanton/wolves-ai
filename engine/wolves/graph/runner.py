from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic_ai.models import Model

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.dossier import build_dossier, previous_agent_anchor
from wolves.agent.publish_surface import PublishSurface, publish_surface
from wolves.agent.tools.submission.submit_forecast import _submit_forecast
from wolves.config import Settings
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import NodeKind, NodeOutcome, NodePatch
from wolves.graph.master import admit, plan_wave
from wolves.graph.nodes import execute_brief
from wolves.graph.research_coverage import (
    add_research_coverage_receipt,
    research_coverage_brief,
    research_coverage_hint,
    should_seed_research,
)
from wolves.graph.reserves import finalisation_reserve_calls, finalisation_reserves_micros
from wolves.observability.runtime import CapExceeded, ObservedRuntime
from wolves.s3.artifacts import ArtifactStore

logger = logging.getLogger(__name__)

_DEMAND_SUBMIT = (
    "Budget or wave limits are nearly exhausted. Stop researching and call submit_forecast now "
    "with your best current forecast; note the pressure in the justification text if it constrained you."
)

_STRUCTURAL_REPAIR_BRIEF = (
    "The last submission was rejected for a structural defect only quant can fix. Brief a quant node to reuse the "
    "cited mixture's existing worlds and weights unchanged and recompute only the missing factor_audit rows "
    "(e.g. a mixture_spread row from wq.mixture_spread), then re-register; no new world simulation is needed."
)


@dataclass(frozen=True)
class GraphModels:
    """The models a run executes on; always ObservedModel-wrapped in live mode."""

    master: Model
    nodes: Mapping[NodeKind, Model]

    @classmethod
    def uniform(cls, model: Model) -> GraphModels:
        kinds: tuple[NodeKind, ...] = ("research", "quant", "forecast", "critic")
        return cls(master=model, nodes=dict.fromkeys(kinds, model))


@dataclass
class GraphRunResult:
    submission: ForecastSubmission | None
    escalations: list[str] | None = None
    budget_exhausted: bool = False
    waves: int = 0
    validation_failures: int = 0
    revisions_used: int = 0
    finalised_with_open_branches: bool = False


def _kickoff(deps: AgentDeps, as_of: str) -> str:
    lessons = deps.memory.read_lessons().strip() or "(empty)"
    journal = (deps.memory.read_latest_journal() or "").strip() or "(none)"
    dossier = build_dossier(deps).strip() or "(no deterministic dossier this run)"
    return (
        f"Today is {as_of}. Focus team: {deps.settings.focus_team}. Produce today's forecast.\n\n"
        f"Dossier:\n{dossier}\n\n"
        f"Lessons:\n{lessons}\n\nLatest journal:\n{journal}"
    )


def _cap_exceeded(exc: Exception) -> bool:
    if isinstance(exc, CapExceeded):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(isinstance(e, CapExceeded) for e in exc.exceptions)
    return False


def _budget_at_caps(runtime: ObservedRuntime, *, reserve_micros: int = 0, reserve_calls: int = 0) -> bool:
    """True once spend crosses the caps minus a reserve held back for a final forecast."""
    budget, caps = runtime.budget, runtime.caps
    if budget.llm_calls >= caps.max_llm_calls - reserve_calls:
        return True
    return bool(caps.max_cost_micros) and budget.cost_micros >= caps.max_cost_micros - reserve_micros


def _finalisation_reserve(deps: AgentDeps) -> int:
    return sum(finalisation_reserves_micros(deps.settings, deps.runtime.caps))


async def _execute_wave(
    ops: list[NodePatch],
    *,
    deps: AgentDeps,
    store: RunArtifactStore,
    models: GraphModels,
) -> list[NodeOutcome]:
    semaphore = asyncio.Semaphore(deps.settings.graph_max_wave_workers)

    async def run_one(op: NodePatch) -> NodeOutcome:
        async with semaphore:
            return await execute_brief(op, deps=deps, store=store, model=models.nodes[op.kind])

    return list(await asyncio.gather(*(run_one(op) for op in ops)))


async def _submit_clean_preview(deps: AgentDeps) -> None:
    checked = deps.submission.checked_clean
    if checked is None or deps.submission.accepted is not None:
        return
    tool_deps = dataclasses.replace(deps, actor="runner-auto-submit")
    result = await _submit_forecast(checked, tool_deps)
    deps.runtime.emit(
        "tool_call",
        "runner-auto-submit",
        f"submit_forecast {'ok' if result.ok else 'error'}",
        tool="submit_forecast",
        ok=result.ok,
    )


def _can_seed_research(settings: Settings) -> bool:
    return (
        settings.graph_max_waves > 0
        and settings.graph_max_nodes > 0
        and settings.graph_max_research_nodes > 0
        and settings.graph_max_wave_workers > 0
    )


def _seeded_research_model(models: GraphModels, hint_level: str) -> Model:
    if hint_level == "standard_suggested":
        return models.nodes["quant"]
    return models.nodes["research"]


def _reset_forecast_copy_state(deps: AgentDeps) -> None:
    deps.submission.copy_repair_required = False
    deps.submission.copy_issue_signature = None
    deps.submission.copy_issue_repeats = 0
    deps.submission.copy_repair_blocked = False
    deps.submission.publication_blocked = False


def _sync_publishable_artifacts(deps: AgentDeps, board: Blackboard) -> None:
    active = board.active_artifact_ids(kinds={"mixture", "forecast"})
    deps.submission.publishable_artifact_ids = active
    if not active:
        return
    last_clean = deps.submission.last_clean
    if last_clean is not None and last_clean.artifact_id not in active:
        deps.submission.last_clean = None
        deps.submission.last_clean_escalations.clear()
    last_accepted = deps.submission.last_accepted
    if last_accepted is not None and last_accepted.artifact_id not in active:
        deps.submission.last_accepted = None


def _has_registered_repair_mixture(outcomes: list[NodeOutcome], store: RunArtifactStore) -> bool:
    return any(
        outcome.ok
        and outcome.kind == "quant"
        and any(
            (record := store.record(artifact_id)) is not None and record.kind == "mixture"
            for artifact_id in outcome.artifact_ids
        )
        for outcome in outcomes
    )


def _published_titles_context(surface: PublishSurface, *, top_n: int = 8) -> str:
    """Compact top-N title JSON for the master; set_context stores str only."""
    ranked = sorted(surface.published_titles.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [{"team": team, "pct": round(p * 100, 1)} for team, p in ranked[:top_n]]
    return json.dumps(top, ensure_ascii=False)


def _has_fresh_premortem(deps: AgentDeps) -> bool:
    """True when a critique artifact exists and the accepted mixture is unreviewed."""
    store = deps.artifacts
    accepted = deps.submission.accepted
    if store is None or accepted is None:
        return False
    fingerprint = accepted.artifact_id
    if fingerprint in deps.submission.premortem_seen:
        return False
    return any(record.kind == "critique" for record in store.all())


def _should_continue_after_acceptance(deps: AgentDeps, board: Blackboard) -> tuple[bool, str]:
    """Re-open an accepted submission once for revision; clears checked_clean so the stale mixture cannot re-submit."""
    settings = deps.settings
    submission_state = deps.submission
    accepted = submission_state.accepted
    if accepted is None:
        return False, "no accepted submission"
    if settings.graph_max_revisions <= 0:
        return False, "revisions disabled"
    if submission_state.revisions_used >= settings.graph_max_revisions:
        return False, "revision budget spent"
    if _budget_at_caps(
        deps.runtime,
        reserve_micros=min(
            int(settings.graph_revision_reserve_usd * 1_000_000)
            + finalisation_reserves_micros(settings, deps.runtime.caps)[1],
            deps.runtime.caps.max_cost_micros // 2,
        ),
        reserve_calls=sum(finalisation_reserve_calls(settings, deps.runtime.caps)),
    ):
        return False, "budget within revision reserve"
    if not _has_fresh_premortem(deps):
        return False, "no fresh pre-mortem to review"
    surface = publish_surface(deps, accepted.artifact_id)
    if surface is None:
        return False, "published surface unavailable"

    if submission_state.counterfactual is None:
        submission_state.counterfactual = accepted
    submission_state.last_accepted = accepted
    submission_state.premortem_seen.add(accepted.artifact_id)
    board.set_context("published_surface", _published_titles_context(surface))
    submission_state.accepted = None
    submission_state.checked_clean = None
    submission_state.escalation_fired = False
    _reset_forecast_copy_state(deps)
    submission_state.revisions_used += 1
    deps.runtime.emit(
        "revision",
        "runner",
        f"re-opened accepted forecast for revision {submission_state.revisions_used}",
        artifact_id=accepted.artifact_id,
        revisions_used=submission_state.revisions_used,
    )
    return True, "re-opening for one revision turn"


async def run_graph(deps: AgentDeps, *, as_of: str, models: GraphModels) -> GraphRunResult:
    """The wave loop: plan, admit, execute, merge, until acceptance or caps."""
    store = deps.artifacts or RunArtifactStore(ArtifactStore(deps.settings), run_id=deps.runtime.run_id)
    deps.artifacts = store
    continuity_anchor = previous_agent_anchor(deps, top_n=6)
    coverage_hint = research_coverage_hint(deps, as_of=as_of)
    board = Blackboard(
        artifacts=store,
        ledger=deps.ledger,
        runtime=deps.runtime,
        source_memory=deps.source_memory,
        run_context={
            "focus_team": deps.settings.focus_team,
            "research_coverage_hint": coverage_hint.digest(),
            **({"continuity_anchor": continuity_anchor} if continuity_anchor else {}),
        },
        settings=deps.settings,
    )
    settings = deps.settings
    submission_state = deps.submission
    budget_exhausted = False
    _sync_publishable_artifacts(deps, board)

    with deps.runtime.run_trace(title=f"forecast {as_of}"):
        if _can_seed_research(settings) and should_seed_research(coverage_hint):
            op = NodePatch(
                node_id="coverage-research",
                kind="research",
                objective="Advisory coverage scan",
                brief=research_coverage_brief(coverage_hint, as_of=as_of),
            )
            outcome = await execute_brief(
                op,
                deps=deps,
                store=store,
                model=_seeded_research_model(models, coverage_hint.level),
            )
            board.merge([op], [outcome], advance_wave=False)
            receipt_id = add_research_coverage_receipt(store, hint=coverage_hint, outcome=outcome)
            board.set_context("research_coverage_receipt", receipt_id)
        else:
            receipt_id = add_research_coverage_receipt(store, hint=coverage_hint)
            board.set_context("research_coverage_receipt", receipt_id)
        for wave in range(settings.graph_max_waves):
            board_summary = board.summary()
            prompt = board_summary if wave else f"{_kickoff(deps, as_of)}\n\nBlackboard:\n{board_summary}"
            try:
                patch = await plan_wave(
                    prompt,
                    board_summary=board_summary,
                    model=models.master,
                    settings=settings,
                    runtime=deps.runtime,
                )
            except Exception as exc:
                if not _cap_exceeded(exc):
                    raise
                logger.warning("master plan stopped by cap: %s", exc)
                budget_exhausted = True
                break
            deps.runtime.emit(
                "graph_patch",
                "master",
                f"wave {board.wave + 1}: {len(patch.ops)} op(s)" + (", stop" if patch.stop else ""),
                ops=[op.model_dump(mode="json") for op in patch.ops],
                reason=patch.reason,
                stop=patch.stop,
            )
            ops, dropped = admit(patch, board=board, settings=settings)
            board.dropped = dropped
            if dropped:
                deps.runtime.emit("admission", "master", f"{len(dropped)} op(s) dropped", drops=dropped)
            if not ops:
                if patch.stop or not patch.ops:
                    logger.info("master stopped after wave %d: %s", board.wave, patch.reason or "empty wave")
                    break
                # Every proposed op was dropped; the drops are on the
                # blackboard, so give the master another planning turn.
                logger.warning("wave %d fully dropped at admission; re-planning", board.wave)
                continue
            if any(op.kind == "forecast" for op in ops):
                _reset_forecast_copy_state(deps)
            had_referee_replan = submission_state.referee_replan_required
            had_structural_repair = submission_state.structural_repair_required
            outcomes = await _execute_wave(ops, deps=deps, store=store, models=models)
            board.merge(ops, outcomes)
            _sync_publishable_artifacts(deps, board)
            await _submit_clean_preview(deps)
            if submission_state.publication_blocked and not submission_state.referee_replan_required:
                logger.info("publication blocked after wave %d", board.wave)
                break
            if submission_state.referee_replan_required:
                follow_up_ran = had_referee_replan and any(
                    outcome.ok and outcome.kind in {"research", "quant"} for outcome in outcomes
                )
                if follow_up_ran:
                    submission_state.referee_replan_required = False
                else:
                    logger.info("referee requested master replanning after wave %d", board.wave)
                    continue
            if submission_state.structural_repair_required:
                mixture_registered = had_structural_repair and _has_registered_repair_mixture(outcomes, store)
                if mixture_registered:
                    submission_state.structural_repair_required = False
                    board.set_context("structural_repair", "")
                else:
                    board.set_context("structural_repair", _STRUCTURAL_REPAIR_BRIEF)
                    logger.info("structural repair requested after wave %d; replanning quant", board.wave)
                    continue
            if patch.stop:
                # A stop patch may carry final ops; they run before the end.
                logger.info("master stopped after wave %d: %s", board.wave, patch.reason or "stop")
                break
            if submission_state.accepted is not None:
                reopen, reason = _should_continue_after_acceptance(deps, board)
                if not reopen:
                    break
                logger.info("post-acceptance revision after wave %d: %s", board.wave, reason)
                continue
            if submission_state.validation_failures > settings.agent_submit_retries:
                logger.error("submission retries exhausted after %d failures", submission_state.validation_failures)
                break
            if not deps.runtime.can_fund_followup_call(
                hold_back_micros=_finalisation_reserve(deps),
                hold_back_calls=sum(finalisation_reserve_calls(settings, deps.runtime.caps)),
                floor_micros=int(settings.graph_followup_floor_usd * 1_000_000),
            ):
                logger.warning("no budget for a follow-up wave after wave %d; finalising on reserve", board.wave)
                budget_exhausted = True
                break

        # Restore before the final-chance block reads accepted is None.
        if (
            submission_state.accepted is None
            and submission_state.last_accepted is not None
            and (
                not submission_state.publishable_artifact_ids
                or submission_state.last_accepted.artifact_id in submission_state.publishable_artifact_ids
            )
        ):
            logger.info("revision did not re-accept; publishing the prior accepted submission")
            submission_state.accepted = submission_state.last_accepted

        if (
            submission_state.accepted is None
            and not submission_state.publication_blocked
            and not submission_state.referee_replan_required
        ):
            # No wave remains to price an open branch, so coverage must not gate the reserve-funded last forecast.
            op = NodePatch(
                node_id="runner-demand-submit",
                kind="forecast",
                objective="Submit the final forecast",
                brief=_DEMAND_SUBMIT,
                input_artifact_ids=[
                    record.id
                    for record in store.all()
                    if record.kind not in {"mixture", "forecast"}
                    or record.id in submission_state.publishable_artifact_ids
                ],
            )
            try:
                _reset_forecast_copy_state(deps)
                outcome = await execute_brief(op, deps=deps, store=store, model=models.nodes["forecast"])
            except Exception as exc:
                if not _cap_exceeded(exc):
                    raise
                logger.warning("demand-submit stopped by cap: %s", exc)
            else:
                board.merge([op], [outcome])
                _sync_publishable_artifacts(deps, board)
                await _submit_clean_preview(deps)

        return GraphRunResult(
            submission=submission_state.accepted,
            escalations=submission_state.escalations or None,
            budget_exhausted=budget_exhausted,
            waves=board.wave,
            validation_failures=submission_state.validation_failures,
            revisions_used=submission_state.revisions_used,
            finalised_with_open_branches=board.branch_coverage().needs_follow_up,
        )
