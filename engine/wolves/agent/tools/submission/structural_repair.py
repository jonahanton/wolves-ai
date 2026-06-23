from __future__ import annotations

from typing import Any

from wolves.agent.deps import AgentDeps
from wolves.agent.validator import ValidationReport
from wolves.toolkit.result import ToolError, ToolResult


def structural_repair_result(
    report: ValidationReport,
    deps: AgentDeps,
    *,
    artifact_id: str,
) -> ToolResult[Any] | None:
    quant_issues = report.quant_repair_issues
    if not quant_issues:
        return None
    if deps.submission.structural_repair_attempts >= deps.settings.agent_structural_repair_attempts:
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
                f"The cited artifact {artifact_id} has a structural artifact issue only a quant node can fix: "
                f"{summary} "
                "Stop this forecast attempt so the master can brief quant to register a replacement artifact."
            ),
        ),
    )
