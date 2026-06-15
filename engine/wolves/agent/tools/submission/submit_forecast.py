from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission._validation import spread_section, validation_report
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


def _remaining_hard(deps: AgentDeps) -> int:
    return max(deps.settings.agent_submit_retries + 1 - deps.submission.validation_failures, 0)


async def _submit_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    report = validation_report(args, deps)
    if not report.ok:
        deps.submission.checked_clean = None
        # Copy issues are repair prompts; only hard issues spend a retry.
        if report.hard_issues:
            deps.submission.copy_repair_required = False
            deps.submission.validation_failures += 1
            cost_note = f"{_remaining_hard(deps)} hard resubmissions remain"
        else:
            deps.submission.copy_repair_required = True
            cost_note = f"copy issues only, no hard retry spent; {_remaining_hard(deps)} hard resubmissions remain"
        deps.runtime.emit("validation", deps.actor, f"submission rejected: {report.summary()[:200]}")
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="validation_failed",
                message=f"Submission rejected. Fix and resubmit: {report.summary()} ({cost_note}).",
            ),
        )

    if report.escalations and not deps.submission.escalation_fired:
        deps.submission.checked_clean = None
        deps.submission.copy_repair_required = False
        deps.submission.escalation_fired = True
        deps.submission.last_clean = args
        deps.submission.last_clean_escalations = report.escalations
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
    grounded = bool(args.evidence_ids) or bool(args.market_justification.strip())
    if deps.submission.escalation_fired and not (args.change_justification.strip() and grounded):
        # Once an escalation fires, the steelman substance is required even if
        # the resubmission swaps in a quieter artifact; the move was flagged.
        deps.submission.copy_repair_required = False
        deps.submission.validation_failures += 1
        deps.runtime.emit("validation", deps.actor, "escalated resubmission without substance rejected")
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="escalation_unsubstantiated",
                message=(
                    "A resubmission past the escalation must carry the steelman in change_justification and "
                    "name its grounds: ledger ids in evidence_ids for news-driven moves, or the computing "
                    f"artifact in market_justification for analysis-driven ones. "
                    f"({_remaining_hard(deps)} hard resubmissions remain.)"
                ),
            ),
        )

    deps.submission.checked_clean = None
    deps.submission.copy_repair_required = False
    deps.submission.accepted = args
    deps.submission.escalations = report.escalations
    deps.runtime.emit("validation", deps.actor, "submission accepted")
    return ToolResult(
        payload={
            "accepted": True,
            "escalations": report.escalations,
            "spread": spread_section(deps, args.artifact_id),
        }
    )


SPEC = ToolSpec(
    name="submit_forecast",
    description=(
        "Submit the final forecast by ARTIFACT REFERENCE: artifact_id names a computed mixture or "
        "simulation artifact from this run (wq.scenario_mixture outputs register automatically); "
        "typed probabilities are never accepted. Carry scenario weights matching the artifact's world "
        "names and weights, with their ledger citations, the run headline, displayed team stories, "
        "and no em-dashes. The "
        "mixture publishes as the headline, unblended. Moves beyond the escalation threshold against "
        "the frozen baseline trigger one steelman pass before acceptance; moves against the previous "
        "published forecast need change_justification or an explicit inconsistency_note; gaps beyond "
        "threshold against the de-vigged market need market_justification naming the computation that "
        "earns them. check_forecast previews this validation for free."
    ),
    args_model=ForecastSubmission,
    fn=_submit_forecast,
)
