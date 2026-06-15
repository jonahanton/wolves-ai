from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission._validation import (
    branch_advisories,
    branch_audit_section,
    factor_audit_section,
    market_gap_contract,
    published_title_preview,
    spread_section,
    validation_report,
    world_metadata_section,
)
from wolves.agent.tools.submission.normalise import normalise_submission, note_copy_repair_state
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


async def _check_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    normalised = normalise_submission(args, deps)
    checked = normalised.submission
    report = validation_report(checked, deps)
    copy_repeats = note_copy_repair_state(report, deps)
    deps.submission.checked_clean = checked if report.ok else None
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
            "copy_issue_repeats": copy_repeats,
            "normalisation_warnings": normalised.warnings,
            "would_pause_for_steelman": bool(report.escalations) and not deps.submission.escalation_fired,
            "published_preview": published_title_preview(deps, checked.artifact_id),
            "spread": spread_section(deps, checked.artifact_id),
            "factor_audit": factor_audit_section(deps, checked.artifact_id),
            "market_gap_contract": market_gap_contract(deps, checked),
            "branch_audit": branch_audit_section(deps, checked.artifact_id),
            "world_metadata": world_metadata_section(deps, checked.artifact_id),
            "advisories": branch_advisories(deps, checked.artifact_id),
            "next_action": (
                "Write the journal if still needed, then call submit_forecast with this checked payload."
                if report.ok
                else (
                    "The same copy issues repeated three times. Stop this forecast attempt and return a short "
                    "ForecastOutput summary so the master can replan finalisation."
                    if deps.submission.copy_repair_blocked
                    else "Fix exactly the listed issues before using any other tool."
                )
            ),
        }
    )


SPEC = ToolSpec(
    name="check_forecast",
    description=(
        "Free preview of the submit validator: takes the same arguments as submit_forecast and returns the "
        "full report (every issue with its severity, plus the escalation diffs against the frozen baseline, "
        "the previous published forecast and the de-vigged market) without recording a submission, spending "
        "a resubmission or firing the steelman pause. The published_preview.titles block is the final title "
        "surface after any calibration governor; quote those numbers and ranks in prose. raw_titles are the "
        "ungoverned mixture and baseline_titles are the governor anchor, so if active=true explain published "
        "numbers as governed rather than as the raw mixture alone. The factor_audit, branch_audit and "
        "world_metadata blocks echo the cited mixture's machine-readable checks and world presentation when "
        "present. Use them to triage a draft before submit_forecast."
    ),
    args_model=ForecastSubmission,
    fn=_check_forecast,
)
