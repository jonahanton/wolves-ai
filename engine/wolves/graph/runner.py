from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic_ai.models import Model

from wolves.agent.consensus import median_overrides
from wolves.agent.contracts import Disagreement, ForecastSubmission, OverrideSample, RatingOverride
from wolves.agent.deps import AgentDeps
from wolves.agent.validator import validate_submission
from wolves.graph.artifacts import ArtifactStore
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import Brief, NodeKind, NodeOutcome
from wolves.graph.master import admit, plan_wave
from wolves.graph.nodes import execute_brief
from wolves.observability.runtime import CapExceeded, ObservedRuntime

logger = logging.getLogger(__name__)

_DEMAND_SUBMIT = (
    "Budget or wave limits are nearly exhausted. Stop researching and call submit_forecast now "
    "with your best current forecast; note the pressure in the justification text if it constrained you."
)
_EXTRACTION_SYSTEM = (
    "You are re-deriving the final rating overrides for a World Cup forecast from a finished "
    "research dossier. Read the ledger evidence and the draft submission, then return the rating "
    "override set the evidence best supports. Respect the caps: confirmed single cause at most 50 Elo, "
    "soft evidence at most 10 Elo total per team, rumours zero. Cite the same ledger ids."
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
    disagreement: Disagreement | None
    budget_exhausted: bool = False
    waves: int = 0
    validation_failures: int = 0


def _kickoff(deps: AgentDeps, as_of: str) -> str:
    lessons = deps.memory.read_lessons().strip() or "(empty)"
    journal = (deps.memory.read_latest_journal() or "").strip() or "(none)"
    return f"Today is {as_of}. Produce today's forecast.\n\nLESSONS.md:\n{lessons}\n\nLatest journal:\n{journal}"


def _cap_exceeded(exc: Exception) -> bool:
    if isinstance(exc, CapExceeded):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(isinstance(e, CapExceeded) for e in exc.exceptions)
    return False


def _budget_at_caps(runtime: ObservedRuntime) -> bool:
    budget, caps = runtime.budget, runtime.caps
    if budget.llm_calls >= caps.max_llm_calls:
        return True
    return bool(caps.max_cost_micros) and budget.cost_micros >= caps.max_cost_micros


async def _execute_wave(
    briefs: list[Brief],
    *,
    deps: AgentDeps,
    store: ArtifactStore,
    models: GraphModels,
) -> list[NodeOutcome]:
    semaphore = asyncio.Semaphore(deps.settings.graph_max_wave_workers)

    async def run_one(brief: Brief) -> NodeOutcome:
        async with semaphore:
            return await execute_brief(brief, deps=deps, store=store, model=models.nodes[brief.kind])

    return list(await asyncio.gather(*(run_one(b) for b in briefs)))


async def run_graph(deps: AgentDeps, *, as_of: str, models: GraphModels) -> GraphRunResult:
    """The wave loop: plan, admit, execute, merge, until acceptance or caps."""
    store = ArtifactStore(deps.runtime.paths.root / "artifacts")
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    settings = deps.settings
    submission_state = deps.submission
    budget_exhausted = False

    with deps.runtime.run_trace(title=f"forecast {as_of}"):
        for wave in range(settings.graph_max_waves):
            prompt = board.summary() if wave else f"{_kickoff(deps, as_of)}\n\nBlackboard:\n{board.summary()}"
            try:
                plan = await plan_wave(prompt, model=models.master)
            except Exception as exc:
                if not _cap_exceeded(exc):
                    raise
                logger.warning("master plan stopped by cap: %s", exc)
                budget_exhausted = True
                break
            briefs = admit(plan, board=board, settings=settings)
            if plan.stop or not briefs:
                logger.info("master stopped after wave %d: %s", board.wave, plan.reason or "empty wave")
                break
            outcomes = await _execute_wave(briefs, deps=deps, store=store, models=models)
            board.merge(briefs, outcomes)
            if submission_state.accepted is not None:
                break
            if submission_state.validation_failures > settings.agent_submit_retries:
                logger.error("submission retries exhausted after %d failures", submission_state.validation_failures)
                break
            if _budget_at_caps(deps.runtime):
                logger.warning("budget at caps after wave %d; stopping", board.wave)
                budget_exhausted = True
                break

        retries_left = submission_state.validation_failures <= settings.agent_submit_retries
        if submission_state.accepted is None and not budget_exhausted and retries_left:
            brief = Brief(
                node_id="runner-demand-submit",
                kind="forecast",
                objective="Submit the final forecast",
                brief=_DEMAND_SUBMIT,
                input_artifact_ids=[a.id for a in store.all()],
            )
            outcome = await execute_brief(brief, deps=deps, store=store, model=models.nodes["forecast"])
            board.merge([brief], [outcome])

        if submission_state.accepted is None:
            return GraphRunResult(
                submission=None,
                disagreement=None,
                budget_exhausted=budget_exhausted,
                waves=board.wave,
                validation_failures=submission_state.validation_failures,
            )

        submission, disagreement = await _k_sample(deps)
        return GraphRunResult(
            submission=submission,
            disagreement=disagreement,
            budget_exhausted=budget_exhausted,
            waves=board.wave,
            validation_failures=submission_state.validation_failures,
        )


async def _k_sample(deps: AgentDeps) -> tuple[ForecastSubmission, Disagreement]:
    """Rerun only the final override extraction over the same dossier and take
    the per-team median; the spread is the run's disagreement metric."""
    accepted = deps.submission.accepted
    assert accepted is not None
    k = max(1, deps.settings.agent_k_samples)
    samples: list[list[RatingOverride]] = [accepted.rating_overrides]
    dossier = _dossier(deps, accepted)

    for _ in range(k - 1):
        try:
            sample = await deps.llm.structured(
                prompt_name="override_extraction",
                actor="consensus",
                response_model=OverrideSample,
                user=dossier,
                system=_EXTRACTION_SYSTEM,
                max_tokens=1500,
                temperature=0.5,
            )
        except CapExceeded:
            logger.warning("k-sample stopped early by cap after %d sample(s)", len(samples))
            break
        samples.append(sample.rating_overrides)

    medians, disagreement = median_overrides(samples)
    candidate = accepted.model_copy(update={"rating_overrides": medians})
    report = validate_submission(candidate, ledger=deps.ledger, limits=deps.limits)
    if not report.ok:
        logger.warning("median override set failed validation (%s); keeping accepted set", report.summary())
        return accepted, disagreement
    return candidate, disagreement


def _dossier(deps: AgentDeps, accepted: ForecastSubmission) -> str:
    entries = "\n".join(e.model_dump_json() for e in deps.ledger.all())
    return (
        f"Evidence ledger:\n{entries or '(empty)'}\n\n"
        f"Draft submission:\n{accepted.model_dump_json(indent=1)}\n\n"
        "Return the final rating override set."
    )
