from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.validator import validate_submission
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult


def _tripwire(submission: ForecastSubmission, deps: AgentDeps) -> str | None:
    threshold = deps.settings.tripwire_threshold
    reasons: list[str] = []
    if abs(submission.delta_vs_market) > threshold:
        reasons.append(f"divergence from market of {submission.delta_vs_market:+.3f}")
    if abs(submission.delta_vs_yesterday) > threshold:
        reasons.append(f"day-over-day swing of {submission.delta_vs_yesterday:+.3f}")
    return " and ".join(reasons) if reasons else None


async def _submit_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    report = validate_submission(args, ledger=deps.ledger, limits=deps.limits)
    if not report.ok:
        deps.validation_failures += 1
        deps.runtime.emit("validation", deps.actor, f"submission rejected: {report.summary()[:200]}")
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="validation_failed", message=f"Submission rejected. Fix and resubmit: {report.summary()}"
            ),
        )

    tripped = None if deps.tripwire_fired else _tripwire(args, deps)
    if tripped is not None:
        deps.tripwire_fired = True
        deps.runtime.emit("tripwire", deps.actor, f"tripwire: {tripped}")
        return ToolResult(
            payload={
                "accepted": False,
                "tripwire": (
                    f"Tripwire, not a veto: your submission carries a {tripped}. "
                    "Steelman the opposite case, then call submit_forecast again, "
                    "either revised or unchanged with your reasoning in the justification text."
                ),
            }
        )

    deps.accepted = args
    deps.runtime.emit("validation", deps.actor, "submission accepted")
    return ToolResult(payload={"accepted": True})


SPEC = ToolSpec(
    name="submit_forecast",
    description=(
        "Submit the final forecast. This is the only way to finish the run. The harness validates: "
        "coherent probabilities; every rating override within caps (confirmed single cause at most 50 Elo, "
        "soft evidence at most 10 Elo total per team, rumours zero) and citing confirmed or probable ledger ids; "
        "fixture offsets with ISO expiry dates; the England daily story, one rationale per R32 slot and the "
        "travel memo, with no em-dashes; and justification text when you diverge from market or yesterday."
    ),
    args_model=ForecastSubmission,
    fn=_submit_forecast,
)
