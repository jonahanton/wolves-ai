from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.validator import validate_submission
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

_BASELINE_SIMS = 50_000


def _baseline_titles(deps: AgentDeps) -> dict[str, float] | None:
    if deps.forecaster is None:
        return None
    return deps.forecaster.title_probs(n_sims=_BASELINE_SIMS, seed=0)


def _previous_titles(deps: AgentDeps) -> dict[str, float] | None:
    from datetime import date

    from wolves.insights.what_changed import load_latest_snapshot

    if not deps.as_of:
        return None
    previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of))
    if previous is None:
        return None
    return {t.team_id: t.champion_prob for t in previous.teams}


async def _submit_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    report = validate_submission(
        args,
        artifacts=deps.artifacts,
        ledger=deps.ledger,
        limits=deps.limits,
        baseline_titles=_baseline_titles(deps),
        previous_titles=_previous_titles(deps),
        focus_team=deps.settings.focus_team,
    )
    if not report.ok:
        deps.submission.validation_failures += 1
        deps.runtime.emit("validation", deps.actor, f"submission rejected: {report.summary()[:200]}")
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="validation_failed", message=f"Submission rejected. Fix and resubmit: {report.summary()}"
            ),
        )

    if report.escalations and not deps.submission.escalation_fired:
        deps.submission.escalation_fired = True
        deps.runtime.emit("escalation", deps.actor, f"escalation: {'; '.join(report.escalations)[:200]}")
        return ToolResult(
            payload={
                "accepted": False,
                "escalation": (
                    "Escalation, not a veto: the artifact moves beyond the threshold vs the frozen baseline "
                    f"({'; '.join(report.escalations)}). Steelman the opposite case, naming the evidence and "
                    "the computation behind each move, then call submit_forecast again, revised or unchanged "
                    "with the steelman in change_justification."
                ),
            }
        )
    if deps.submission.escalation_fired and not (args.change_justification.strip() and args.evidence_ids):
        # Once an escalation fires, the steelman substance is required even if
        # the resubmission swaps in a quieter artifact; the move was flagged.
        deps.submission.validation_failures += 1
        deps.runtime.emit("validation", deps.actor, "escalated resubmission without substance rejected")
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="escalation_unsubstantiated",
                message=(
                    "A resubmission past the escalation must name its evidence (evidence_ids citing ledger "
                    "entries) and carry the steelman in change_justification."
                ),
            ),
        )

    deps.submission.accepted = args
    deps.submission.escalations = report.escalations
    deps.runtime.emit("validation", deps.actor, "submission accepted")
    return ToolResult(payload={"accepted": True, "escalations": report.escalations})


SPEC = ToolSpec(
    name="submit_forecast",
    description=(
        "Submit the final forecast by ARTIFACT REFERENCE: artifact_id names a computed mixture or "
        "simulation artifact from this run (wq.scenario_mixture outputs register automatically); "
        "typed probabilities are never accepted. Carry the named scenario weights with their ledger "
        "citations, the focus team daily story, one rationale per R32 slot and the travel memo, no "
        "em-dashes. Moves beyond the escalation threshold against the frozen baseline trigger one "
        "steelman pass before acceptance; moves against the previous published forecast need "
        "change_justification or an explicit inconsistency_note."
    ),
    args_model=ForecastSubmission,
    fn=_submit_forecast,
)
