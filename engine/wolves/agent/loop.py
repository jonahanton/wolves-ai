"""The master agent loop: one Claude agent, rich tools, hard boundary.

The loop owns turn-taking, the demand-to-submit near budget exhaustion and
the K-sample consensus after acceptance. The validator and tripwires live in
the submit tool so their feedback reaches the model inside the loop."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from wolves.agent._dispatch import dispatch_tool_uses
from wolves.agent.consensus import median_overrides
from wolves.agent.contracts import Disagreement, ForecastSubmission, OverrideSample, RatingOverride
from wolves.agent.deps import AgentDeps
from wolves.agent.tools import master_toolset
from wolves.agent.validator import validate_submission
from wolves.agent_tools.adapters.anthropic import to_anthropic_tools
from wolves.observability.runtime import CapExceeded

logger = logging.getLogger(__name__)

_PROMPT = (Path(__file__).parent / "prompts" / "master.md").read_text(encoding="utf-8")

_CONTINUE = "You are not finished. The only way to complete the run is to call submit_forecast."
_DEMAND_SUBMIT = (
    "Budget is nearly exhausted. Stop researching and call submit_forecast now with your "
    "best current forecast; note budget pressure in the justification text if it constrained you."
)
_EXTRACTION_SYSTEM = (
    "You are re-deriving the final rating overrides for a World Cup forecast from a finished "
    "research dossier. Read the ledger evidence and the draft submission, then return the rating "
    "override set the evidence best supports. Respect the caps: confirmed single cause at most 50 Elo, "
    "soft evidence at most 10 Elo total per team, rumours zero. Cite the same ledger ids."
)


@dataclass
class MasterRunResult:
    submission: ForecastSubmission | None
    disagreement: Disagreement | None
    budget_exhausted: bool = False
    turns: int = 0
    validation_failures: int = 0


def _kickoff(deps: AgentDeps, as_of: str) -> str:
    lessons = deps.memory.read_lessons().strip() or "(empty)"
    journal = (deps.memory.read_latest_journal() or "").strip() or "(none)"
    return f"Today is {as_of}. Produce today's forecast.\n\nLESSONS.md:\n{lessons}\n\nLatest journal:\n{journal}"


async def run_master(deps: AgentDeps, *, as_of: str) -> MasterRunResult:
    """Run the full forecast loop and return the consensus submission."""
    specs = master_toolset()
    tools = to_anthropic_tools(specs)
    messages: list[dict] = [{"role": "user", "content": _kickoff(deps, as_of)}]
    settings = deps.settings
    budget_exhausted = False
    turns = 0

    with deps.runtime.run_trace(title=f"forecast {as_of}"):
        for turn_number in range(1, settings.agent_max_turns + 1):
            turns = turn_number
            try:
                turn = await deps.llm.tool_turn(
                    actor=deps.actor,
                    prompt_name="master_loop",
                    messages=messages,
                    tools=tools,
                    system=_PROMPT,
                    max_tokens=4000,
                )
            except CapExceeded as exc:
                logger.warning("master loop stopped by cap: %s", exc)
                budget_exhausted = True
                break

            messages.append({"role": "assistant", "content": turn.content})
            if not turn.tool_use_blocks:
                messages.append({"role": "user", "content": _CONTINUE})
                continue

            results = await dispatch_tool_uses(turn, specs, deps)
            content: list[dict] = list(results)
            if deps.accepted is not None:
                messages.append({"role": "user", "content": content})
                break
            if deps.validation_failures > settings.agent_submit_retries:
                logger.error("submission retries exhausted after %d failures", deps.validation_failures)
                messages.append({"role": "user", "content": content})
                break
            if turn_number >= settings.agent_max_turns - 2:
                content.append({"type": "text", "text": _DEMAND_SUBMIT})
            messages.append({"role": "user", "content": content})

        if deps.accepted is None:
            return MasterRunResult(
                submission=None,
                disagreement=None,
                budget_exhausted=budget_exhausted,
                turns=turns,
                validation_failures=deps.validation_failures,
            )

        submission, disagreement = await _k_sample(deps)
        return MasterRunResult(
            submission=submission,
            disagreement=disagreement,
            budget_exhausted=budget_exhausted,
            turns=turns,
            validation_failures=deps.validation_failures,
        )


async def _k_sample(deps: AgentDeps) -> tuple[ForecastSubmission, Disagreement]:
    """Rerun only the final override extraction over the same dossier and take
    the per-team median; the spread is the run's disagreement metric."""
    accepted = deps.accepted
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
