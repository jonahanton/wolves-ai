from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.models.anthropic import AnthropicModelSettings

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission._validation import (
    branch_advisories,
    branch_audit_section,
    factor_audit_section,
    market_gap_contract,
    published_title_preview,
    spread_section,
    world_metadata_section,
)
from wolves.agent.validator import ValidationReport
from wolves.prompts import prompt

RefereeOwner = Literal["forecast", "master", "research", "quant", "infra"]
RefereeSeverity = Literal["blocker", "major", "minor"]


class RefereeIssue(BaseModel):
    severity: RefereeSeverity
    owner: RefereeOwner
    threshold: str
    message: str
    suggested_next_step: str


class RefereeReport(BaseModel):
    approved: bool
    summary: str
    issues: list[RefereeIssue]
    suggested_master_brief: str

    @property
    def blocking_issues(self) -> list[RefereeIssue]:
        return [issue for issue in self.issues if issue.severity in {"blocker", "major"}]

    @property
    def needs_master_replan(self) -> bool:
        return any(issue.owner in {"master", "research", "quant"} for issue in self.blocking_issues)

    @property
    def terminal_infra_block(self) -> bool:
        return any(issue.owner == "infra" for issue in self.blocking_issues)


_REFEREE = Agent(
    output_type=ToolOutput(RefereeReport, strict=True),
    system_prompt=prompt("referee"),
    output_retries=1,
)
_REFEREE_SETTINGS = AnthropicModelSettings(anthropic_cache="5m", max_tokens=1800)


def submission_fingerprint(args: ForecastSubmission) -> str:
    body = args.model_dump_json()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


async def referee_review(
    args: ForecastSubmission,
    deps: AgentDeps,
    validation: ValidationReport,
) -> RefereeReport:
    if not deps.settings.graph_referee_enabled:
        return RefereeReport(approved=True, summary="referee disabled", issues=[], suggested_master_brief="")
    if deps.referee_model is None:
        deps.runtime.emit("referee", "referee", "referee enabled but no referee model is configured")
        return RefereeReport(
            approved=False,
            summary="referee enabled but unavailable",
            issues=[
                RefereeIssue(
                    severity="blocker",
                    owner="infra",
                    threshold="final referee unavailable",
                    message="The final referee is enabled but no referee model is configured.",
                    suggested_next_step="Fix the referee configuration before launching another forecast.",
                )
            ],
            suggested_master_brief="Referee infrastructure is unavailable; do not replan the forecast.",
        )
    if submission_fingerprint(args) in deps.submission.referee_approved:
        return RefereeReport(approved=True, summary="already approved", issues=[], suggested_master_brief="")
    user = json.dumps(_referee_context(args, deps, validation), ensure_ascii=False, indent=1)
    try:
        model = deps.referee_model.for_actor("referee", operation="referee")
        report = (await _REFEREE.run(user, model=model, model_settings=_REFEREE_SETTINGS)).output
    except Exception as exc:
        deps.runtime.emit("referee", "referee", f"referee unavailable: {exc}")
        return RefereeReport(
            approved=False,
            summary=f"referee unavailable: {exc}",
            issues=[
                RefereeIssue(
                    severity="blocker",
                    owner="infra",
                    threshold="final referee unavailable",
                    message="The final referee could not run, so the submission has not had the required final sweep.",
                    suggested_next_step="Fix the referee client failure before launching another forecast.",
                )
            ],
            suggested_master_brief="Referee infrastructure failed; do not replan the forecast.",
        )
    if not report.blocking_issues:
        report = report.model_copy(update={"approved": True})
        deps.submission.referee_approved.add(submission_fingerprint(args))
    return report


def record_referee_block(report: RefereeReport, deps: AgentDeps) -> str | None:
    if deps.artifacts is None:
        return None
    challenges = [
        f"{issue.owner}: {issue.message} Next: {issue.suggested_next_step}" for issue in report.blocking_issues
    ]
    artifact = deps.artifacts.add(
        kind="critique",
        created_by="referee",
        summary=report.summary[:140],
        payload={
            "summary": report.summary,
            "issues": [issue.model_dump(mode="json") for issue in report.issues],
            "suggested_master_brief": report.suggested_master_brief,
            "challenges": challenges,
        },
    )
    return artifact.id


def _referee_context(args: ForecastSubmission, deps: AgentDeps, validation: ValidationReport) -> dict[str, object]:
    artifact = deps.artifacts.get(args.artifact_id) if deps.artifacts is not None else None
    payload = artifact.payload if artifact is not None else {}
    return {
        "as_of": deps.as_of,
        "focus_team": deps.settings.focus_team,
        "public_surface": _public_surface(args, payload),
        "submission": {
            "artifact_id": args.artifact_id,
            "headline": args.narrative.headline,
            "team_stories": {team: story.model_dump() for team, story in args.narrative.team_stories.items()},
            "scenario_weights": [weight.model_dump() for weight in args.scenario_weights],
            "camps": [camp.model_dump() for camp in args.camps],
            "market_gaps": [gap.model_dump() for gap in args.market_gaps],
            "market_justification": args.market_justification,
            "change_justification": args.change_justification,
            "inconsistency_note": args.inconsistency_note,
            "evidence_ids": args.evidence_ids,
            "news_impacts": args.news_impacts,
        },
        "deterministic_validator": {
            "ok": validation.ok,
            "escalations": validation.escalations,
            "issues": [issue.model_dump() for issue in validation.issues],
        },
        "published_preview": _top_preview(published_title_preview(deps, args.artifact_id)),
        "spread": spread_section(deps, args.artifact_id),
        "factor_audit": factor_audit_section(deps, args.artifact_id),
        "branch_audit": branch_audit_section(deps, args.artifact_id),
        "world_metadata": world_metadata_section(deps, args.artifact_id),
        "market_gap_contract": market_gap_contract(deps, args),
        "advisories": branch_advisories(deps, args.artifact_id),
        "artifact": _artifact_digest(payload),
        "artifact_index": _artifact_index(deps),
        "research_artifacts": _research_artifacts(deps),
        "retrieval_artifacts": _retrieval_artifacts(deps),
        "quant_artifacts": _quant_artifacts(deps),
        "ledger": _ledger_context(args, deps),
        "previous_agent_anchor": _previous_agent_anchor(deps),
    }


def _public_surface(args: ForecastSubmission, payload: dict[str, object]) -> dict[str, object]:
    worlds = _as_dict(payload.get("worlds"))
    bucket_type = "camps" if args.camps else "worlds"
    buckets = _camp_buckets(args) if args.camps else _world_buckets(payload)
    return {
        "headline": args.narrative.headline,
        "team_stories": {team: story.model_dump() for team, story in args.narrative.team_stories.items()},
        "visible_distribution": {
            "bucket_type": bucket_type,
            "bucket_count": len(buckets),
            "raw_world_count": len(worlds),
            "buckets": buckets,
        },
    }


def _camp_buckets(args: ForecastSubmission) -> list[dict[str, object]]:
    return [
        {
            "key": camp.key,
            "label": camp.label,
            "summary": camp.summary,
            "weight": round(sum(weight.weight for weight in args.scenario_weights if weight.camp == camp.key), 6),
        }
        for camp in args.camps
    ]


def _world_buckets(payload: dict[str, object]) -> list[dict[str, object]]:
    weights = _as_dict(payload.get("weights"))
    metadata = _as_dict(payload.get("world_metadata"))
    return [
        {
            "key": name,
            "label": _as_dict(metadata.get(name)).get("label"),
            "summary": _as_dict(metadata.get(name)).get("summary"),
            "weight": weights.get(name),
        }
        for name in _as_dict(payload.get("worlds"))
    ]


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _top_preview(preview: dict[str, object]) -> dict[str, object]:
    ranking = preview.get("ranking")
    if isinstance(ranking, list):
        preview = {**preview, "ranking": ranking[:12]}
    return preview


def _artifact_digest(payload: dict[str, object]) -> dict[str, object]:
    return {
        "weights": payload.get("weights"),
        "world_metadata": payload.get("world_metadata"),
        "branch_audit": payload.get("branch_audit"),
        "factor_audit": payload.get("factor_audit"),
        "worlds": payload.get("worlds"),
        "conditionals": payload.get("conditionals"),
        "noise_floor_pp": payload.get("noise_floor_pp"),
        "priced_items": payload.get("priced_items"),
        "summary": payload.get("summary"),
    }


def _ledger_context(args: ForecastSubmission, deps: AgentDeps) -> list[dict[str, object]]:
    cited = list(args.evidence_ids)
    for weight in args.scenario_weights:
        cited.extend(weight.ledger_ids)
    cited_set = set(cited)
    entries = deps.ledger.all()
    ordered = [
        *[entry for entry in entries if entry.id in cited_set],
        *[
            entry
            for entry in entries
            if entry.id not in cited_set and entry.status in {"confirmed", "probable"} and entry.proposed_delta
        ],
        *[entry for entry in entries if entry.id not in cited_set],
    ]
    out: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in ordered:
        if entry.id in seen:
            continue
        seen.add(entry.id)
        out.append(
            {
                "id": entry.id,
                "team_id": entry.team_id,
                "claim": entry.claim,
                "status": entry.status,
                "source_url": entry.source_url,
                "proposed_delta": entry.proposed_delta,
                "retrieval_id": entry.retrieval_id,
            }
        )
        if len(out) >= 30:
            break
    return out


def _previous_agent_anchor(deps: AgentDeps) -> dict[str, object] | None:
    if deps.disable_continuity or not deps.as_of:
        return None
    from datetime import date

    from wolves.agent.scoring import latest_snapshot_by_kind
    from wolves.snapshot import run_day

    previous = latest_snapshot_by_kind(
        deps.settings.runs_root / "snapshots",
        before=date.fromisoformat(deps.as_of),
        kind="agent",
    )
    if previous is None or previous.agent is None:
        return None
    top = sorted(previous.teams, key=lambda team: team.champion_prob, reverse=True)[:8]
    return {
        "run_id": previous.run.run_id,
        "as_of": run_day(previous.run),
        "title_probs": {team.team_id: team.champion_prob for team in top},
        "scenario_weights": [weight.model_dump(mode="json") for weight in previous.agent.scenario_weights],
        "camps": [camp.model_dump(mode="json") for camp in previous.agent.camps],
        "branch_audit": previous.agent.branch_audit,
        "world_metadata": previous.agent.world_metadata,
        "headline": previous.agent.narrative.headline,
    }


def _artifact_index(deps: AgentDeps) -> list[dict[str, object]]:
    if deps.artifacts is None:
        return []
    return [
        {
            "id": record.id,
            "kind": record.kind,
            "created_by": record.created_by,
            "summary": record.summary,
        }
        for record in deps.artifacts.all()
    ]


def _research_artifacts(deps: AgentDeps) -> list[dict[str, object]]:
    if deps.artifacts is None:
        return []
    out: list[dict[str, object]] = []
    for record in deps.artifacts.all():
        if record.kind != "evidence":
            continue
        artifact = deps.artifacts.get(record.id)
        if artifact is None:
            continue
        signals = artifact.payload.get("signals")
        out.append(
            {
                "id": record.id,
                "summary": artifact.payload.get("summary"),
                "signals": signals[:12] if isinstance(signals, list) else [],
                "candidate_branches": artifact.payload.get("candidate_branches", []),
            }
        )
    return out


def _retrieval_artifacts(deps: AgentDeps) -> list[dict[str, object]]:
    if deps.artifacts is None:
        return []
    out: list[dict[str, object]] = []
    for record in deps.artifacts.all():
        if record.kind != "retrieval":
            continue
        artifact = deps.artifacts.get(record.id)
        if artifact is None:
            continue
        rankings = artifact.payload.get("rankings")
        out.append(
            {
                "id": record.id,
                "sub_question": artifact.payload.get("sub_question"),
                "rankings": rankings[:8] if isinstance(rankings, list) else [],
            }
        )
    return out


def _quant_artifacts(deps: AgentDeps) -> list[dict[str, object]]:
    if deps.artifacts is None:
        return []
    out: list[dict[str, object]] = []
    for record in deps.artifacts.all():
        if record.kind not in {"quant", "mixture", "forecast"}:
            continue
        artifact = deps.artifacts.get(record.id)
        if artifact is None:
            continue
        findings = artifact.payload.get("findings")
        priced_items = artifact.payload.get("priced_items")
        out.append(
            {
                "id": record.id,
                "kind": record.kind,
                "summary": artifact.payload.get("summary") or record.summary,
                "findings": findings[:8] if isinstance(findings, list) else [],
                "priced_items": priced_items[:12] if isinstance(priced_items, list) else [],
                "branch_audit": artifact.payload.get("branch_audit"),
                "factor_audit": artifact.payload.get("factor_audit"),
                "weights": artifact.payload.get("weights"),
            }
        )
    return out
