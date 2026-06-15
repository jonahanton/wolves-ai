from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission._validation import spread_section, validation_report
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


async def _check_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    report = validation_report(args, deps)
    deps.submission.checked_clean = args if report.ok else None
    deps.submission.copy_repair_required = (not report.ok) and not bool(report.hard_issues)
    deps.runtime.emit(
        "validation",
        deps.actor,
        f"forecast preview {'clean' if report.ok else 'rejected'}: {report.summary()[:200]}",
        ok=report.ok,
        issue_count=len(report.issues),
        escalation_count=len(report.escalations),
    )
    return ToolResult(
        payload={
            "ok": report.ok,
            "issues": [issue.model_dump() for issue in report.issues],
            "escalations": report.escalations,
            "would_pause_for_steelman": bool(report.escalations) and not deps.submission.escalation_fired,
            "spread": spread_section(deps, args.artifact_id),
            "next_action": (
                "Write the journal if still needed, then call submit_forecast with this checked payload."
                if report.ok
                else "Fix exactly the listed issues before using any other tool."
            ),
        }
    )


SPEC = ToolSpec(
    name="check_forecast",
    description=(
        "Free preview of the submit validator: takes the same arguments as submit_forecast and returns the "
        "full report (every issue with its severity, plus the escalation diffs against the frozen baseline, "
        "the previous published forecast and the de-vigged market) without recording a submission, spending "
        "a resubmission or firing the steelman pause. Use it to triage a draft before submit_forecast."
    ),
    args_model=ForecastSubmission,
    fn=_check_forecast,
)
