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
    validation_next_action,
    validation_report,
    world_metadata_section,
)
from wolves.agent.tools.submission.normalise import normalise_submission, note_copy_repair_state
from wolves.agent.tools.submission.referee import record_referee_block, referee_review
from wolves.agent.validator import ValidationReport
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


def _remaining_hard(deps: AgentDeps) -> int:
    return max(deps.settings.agent_submit_retries + 1 - deps.submission.validation_failures, 0)


def _structural_repair_result(report: ValidationReport, deps: AgentDeps, *, artifact_id: str) -> ToolResult[Any] | None:
    """Route a quant-owned structural rejection to the master once; a repeat of
    the same signature falls through to the normal hard-retry path."""
    quant_issues = report.quant_repair_issues
    if not quant_issues:
        return None
    signature = (artifact_id, *sorted(issue.code for issue in quant_issues))
    if signature == deps.submission.structural_repair_signature:
        return None
    deps.submission.structural_repair_signature = signature
    deps.submission.structural_repair_required = True
    deps.submission.structural_repair_attempts += 1
    deps.submission.copy_repair_required = False
    summary = "; ".join(issue.message for issue in quant_issues)
    deps.runtime.emit("validation", deps.actor, f"structural repair needed: {report.summary()[:200]}")
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(
            type="structural_repair_required",
            message=(
                f"The cited artifact {artifact_id} has a structural defect only a quant node can fix: {summary} "
                "Stop this forecast attempt and return a short ForecastOutput summary so the master can brief quant "
                "to regenerate the artifact."
            ),
        ),
    )


def _team_named(team: str, text: str) -> bool:
    haystack = text.lower()
    return team.lower() in haystack or team.lower().replace("-", " ") in haystack


def _missing_escalation_teams(args: ForecastSubmission, deps: AgentDeps) -> list[str]:
    teams = [escalation.split()[0] for escalation in deps.submission.last_clean_escalations]
    if not teams:
        return []
    return sorted({team for team in teams if not _team_named(team, args.change_justification)})


def _accept_forecast(
    checked: ForecastSubmission,
    deps: AgentDeps,
    report: ValidationReport,
    normalisation_warnings: list[str],
    *,
    referee_note: str | None = None,
) -> ToolResult[Any]:
    deps.submission.checked_clean = None
    deps.submission.copy_repair_required = False
    deps.submission.referee_replan_required = False
    deps.submission.structural_repair_required = False
    deps.submission.publication_blocked = False
    deps.submission.accepted = checked
    deps.submission.escalations = report.escalations
    deps.runtime.emit(
        "validation",
        deps.actor,
        "submission accepted" if referee_note is None else f"submission accepted ({referee_note})",
    )
    payload: dict[str, Any] = {
        "accepted": True,
        "escalations": report.escalations,
        "normalisation_warnings": normalisation_warnings,
        "published_preview": published_title_preview(deps, checked.artifact_id),
        "spread": spread_section(deps, checked.artifact_id),
        "factor_audit": factor_audit_section(deps, checked.artifact_id),
        "market_gap_contract": market_gap_contract(deps, checked),
        "branch_audit": branch_audit_section(deps, checked.artifact_id),
        "world_metadata": world_metadata_section(deps, checked.artifact_id),
        "advisories": branch_advisories(deps, checked.artifact_id),
    }
    if referee_note is not None:
        payload["referee"] = {"approved": False, "bypassed": True, "reason": referee_note}
    return ToolResult(payload=payload)


async def _submit_forecast(args: ForecastSubmission, deps: AgentDeps) -> ToolResult[Any]:
    normalised = normalise_submission(args, deps)
    checked = normalised.submission
    report = validation_report(checked, deps)
    copy_repeats = note_copy_repair_state(report, deps)
    if not report.ok:
        deps.submission.checked_clean = None
        if structural := _structural_repair_result(report, deps, artifact_id=checked.artifact_id):
            return structural
        # Copy issues are repair prompts; only hard issues spend a retry.
        if report.hard_issues:
            deps.submission.copy_repair_required = False
            deps.submission.validation_failures += 1
            cost_note = f"{_remaining_hard(deps)} hard resubmissions remain"
        else:
            deps.submission.copy_repair_required = not deps.submission.copy_repair_blocked
            cost_note = f"copy issues only, no hard retry spent; {_remaining_hard(deps)} hard resubmissions remain"
        deps.runtime.emit("validation", deps.actor, f"submission rejected: {report.summary()[:200]}")
        if deps.submission.copy_repair_blocked:
            warnings = f" Normalisation applied: {'; '.join(normalised.warnings)}." if normalised.warnings else ""
            return ToolResult(
                ok=False,
                payload=None,
                error=ToolError(
                    type="copy_repair_loop",
                    message=(
                        "The same copy-only validation issues repeated "
                        f"{copy_repeats} times. Stop this forecast attempt and return a short ForecastOutput "
                        "summary so the master can replan finalisation."
                        f"{warnings}"
                    ),
                ),
            )
        warnings = f" Normalisation applied: {'; '.join(normalised.warnings)}." if normalised.warnings else ""
        next_action = validation_next_action(report, copy_repair_blocked=deps.submission.copy_repair_blocked)
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="validation_failed",
                message=(
                    f"Submission rejected. {report.summary()} Next action: {next_action} "
                    f"({cost_note}).{warnings}"
                ),
            ),
        )

    if report.escalations and not deps.submission.escalation_fired:
        deps.submission.checked_clean = None
        deps.submission.copy_repair_required = False
        deps.submission.escalation_fired = True
        deps.submission.last_clean = checked
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
    grounded = bool(checked.evidence_ids) or bool(checked.market_justification.strip())
    missing_escalation_teams = _missing_escalation_teams(checked, deps)
    if deps.submission.escalation_fired and (
        not (checked.change_justification.strip() and grounded) or missing_escalation_teams
    ):
        # Once an escalation fires, the steelman substance is required even if
        # the resubmission swaps in a quieter artifact; the move was flagged.
        deps.submission.copy_repair_required = False
        deps.submission.validation_failures += 1
        deps.runtime.emit("validation", deps.actor, "escalated resubmission without substance rejected")
        team_note = (
            "Address every escalated team in change_justification: "
            f"{', '.join(missing_escalation_teams)}. "
            if missing_escalation_teams
            else ""
        )
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="escalation_unsubstantiated",
                message=(
                    "A resubmission past the escalation must carry the steelman in change_justification and "
                    "name its grounds: ledger ids in evidence_ids for news-driven moves, or the computing "
                    f"artifact in market_justification for analysis-driven ones. {team_note}"
                    f"({_remaining_hard(deps)} hard resubmissions remain.)"
                ),
            ),
        )

    referee = await referee_review(checked, deps, report)
    if referee.blocking_issues:
        artifact_id = record_referee_block(referee, deps)
        if referee.terminal_infra_block:
            deps.runtime.emit(
                "referee",
                "referee",
                f"referee unavailable; publishing clean submission without referee approval: {referee.summary[:160]}",
                artifact_id=artifact_id,
            )
            return _accept_forecast(
                checked,
                deps,
                report,
                normalised.warnings,
                referee_note=f"referee unavailable: {referee.summary}",
            )
        if deps.submission.referee_interventions < deps.settings.graph_referee_max_interventions:
            deps.submission.publication_blocked = True
            deps.submission.referee_interventions += 1
            deps.submission.checked_clean = None
            deps.submission.copy_repair_required = not referee.needs_master_replan
            deps.submission.referee_replan_required = referee.needs_master_replan
            deps.runtime.emit(
                "referee",
                "referee",
                f"referee blocked submission: {referee.summary[:200]}",
                artifact_id=artifact_id,
                needs_master_replan=referee.needs_master_replan,
            )
            if referee.needs_master_replan:
                message = (
                    "The referee found a threshold-crossing issue that needs master replanning. "
                    "Stop this forecast attempt and return a short ForecastOutput summary so the master can open "
                    "the next research or quant wave. "
                    f"Referee: {referee.summary}. Suggested master brief: {referee.suggested_master_brief}"
                )
                error_type = "referee_replan_required"
            else:
                message = f"The referee found a final-copy issue. Fix and resubmit: {referee.summary}"
                error_type = "referee_revision_required"
            return ToolResult(ok=False, payload=None, error=ToolError(type=error_type, message=message))
        deps.runtime.emit(
            "referee",
            "referee",
            "referee intervention limit reached; publishing clean submission without referee approval: "
            f"{referee.summary[:160]}",
            artifact_id=artifact_id,
        )
        return _accept_forecast(
            checked,
            deps,
            report,
            normalised.warnings,
            referee_note=f"referee intervention cap reached: {referee.summary}",
        )

    return _accept_forecast(checked, deps, report, normalised.warnings)


SPEC = ToolSpec(
    name="submit_forecast",
    description=(
        "Submit the final forecast by ARTIFACT REFERENCE: artifact_id names a computed mixture or "
        "simulation artifact from this run (wq.scenario_mixture outputs register automatically); "
        "typed probabilities are never accepted. Carry scenario weights matching the artifact's world "
        "names and weights, with their ledger citations, the run headline, displayed team stories, "
        "and no em-dashes. check_forecast previews the final published numbers and ranking after any calibration "
        "governor; when that preview is active, prose should distinguish the governed published forecast from "
        "the raw mixture. Moves beyond the escalation threshold against "
        "the frozen baseline trigger one steelman pass before acceptance; moves against the previous "
        "published forecast need change_justification or an explicit inconsistency_note; gaps beyond "
        "threshold against the de-vigged market need market_justification naming the computation that "
        "earns them. check_forecast previews this validation for free."
    ),
    args_model=ForecastSubmission,
    fn=_submit_forecast,
)
