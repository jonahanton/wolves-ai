from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic_ai.models import Model

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.dossier import build_dossier
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import NodeKind, NodeOutcome, NodePatch
from wolves.graph.master import admit, plan_wave
from wolves.graph.nodes import execute_brief
from wolves.observability.runtime import CapExceeded, ObservedRuntime
from wolves.s3.artifacts import ArtifactStore

logger = logging.getLogger(__name__)

_DEMAND_SUBMIT = (
    "Budget or wave limits are nearly exhausted. Stop researching and call submit_forecast now "
    "with your best current forecast; note the pressure in the justification text if it constrained you."
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


def _kickoff(deps: AgentDeps, as_of: str) -> str:
    lessons = deps.memory.read_lessons().strip() or "(empty)"
    journal = (deps.memory.read_latest_journal() or "").strip() or "(none)"
    dossier = build_dossier(deps).strip() or "(no deterministic dossier this run)"
    return (
        f"Today is {as_of}. Produce today's forecast.\n\nDossier:\n{dossier}\n\n"
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


async def run_graph(deps: AgentDeps, *, as_of: str, models: GraphModels) -> GraphRunResult:
    """The wave loop: plan, admit, execute, merge, until acceptance or caps."""
    store = deps.artifacts or RunArtifactStore(ArtifactStore(deps.settings), run_id=deps.runtime.run_id)
    deps.artifacts = store
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    settings = deps.settings
    submission_state = deps.submission
    budget_exhausted = False

    with deps.runtime.run_trace(title=f"forecast {as_of}"):
        for wave in range(settings.graph_max_waves):
            prompt = board.summary() if wave else f"{_kickoff(deps, as_of)}\n\nBlackboard:\n{board.summary()}"
            try:
                patch = await plan_wave(prompt, model=models.master)
            except Exception as exc:
                if not _cap_exceeded(exc):
                    raise
                logger.warning("master plan stopped by cap: %s", exc)
                budget_exhausted = True
                break
            ops, dropped = admit(patch, board=board, settings=settings)
            board.dropped = dropped
            if not ops:
                if patch.stop or not patch.ops:
                    logger.info("master stopped after wave %d: %s", board.wave, patch.reason or "empty wave")
                    break
                # Every proposed op was dropped; the drops are on the
                # blackboard, so give the master another planning turn.
                logger.warning("wave %d fully dropped at admission; re-planning", board.wave)
                continue
            outcomes = await _execute_wave(ops, deps=deps, store=store, models=models)
            board.merge(ops, outcomes)
            if patch.stop:
                # A stop patch may carry final ops; they run before the end.
                logger.info("master stopped after wave %d: %s", board.wave, patch.reason or "stop")
                break
            if submission_state.accepted is not None:
                break
            if submission_state.validation_failures > settings.agent_submit_retries:
                logger.error("submission retries exhausted after %d failures", submission_state.validation_failures)
                break
            if _budget_at_caps(
                deps.runtime,
                reserve_micros=int(settings.graph_forecast_reserve_usd * 1_000_000),
                reserve_calls=settings.graph_forecast_reserve_llm_calls,
            ):
                logger.warning("budget within forecast reserve after wave %d; stopping waves", board.wave)
                budget_exhausted = True
                break

        retries_left = submission_state.validation_failures <= settings.agent_submit_retries
        if submission_state.accepted is None and retries_left and not _budget_at_caps(deps.runtime):
            # The reserve held back above funds this last forecast even when the
            # wave loop stopped for budget; a cap mid-submit degrades, not raises.
            op = NodePatch(
                node_id="runner-demand-submit",
                kind="forecast",
                objective="Submit the final forecast",
                brief=_DEMAND_SUBMIT,
                input_artifact_ids=[a.id for a in store.all()],
            )
            try:
                outcome = await execute_brief(op, deps=deps, store=store, model=models.nodes["forecast"])
            except Exception as exc:
                if not _cap_exceeded(exc):
                    raise
                logger.warning("demand-submit stopped by cap: %s", exc)
            else:
                board.merge([op], [outcome])

        return GraphRunResult(
            submission=submission_state.accepted,
            escalations=submission_state.escalations or None,
            budget_exhausted=budget_exhausted,
            waves=board.wave,
            validation_failures=submission_state.validation_failures,
        )
