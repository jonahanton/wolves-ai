from __future__ import annotations

import re
from dataclasses import dataclass

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.tools.submission._validation import (
    factor_audit_section,
    published_title_preview,
    validator_anchors,
)
from wolves.agent.validator import ValidationReport

_PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:])")
_MULTISPACE = re.compile(r"\s{2,}")
_STORY_PERCENT_TOLERANCE_PP = 0.15


@dataclass(frozen=True)
class NormalisedSubmission:
    submission: ForecastSubmission
    warnings: list[str]


def normalise_submission(args: ForecastSubmission, deps: AgentDeps) -> NormalisedSubmission:
    """Apply mechanical repairs that have a single computed source of truth."""
    warnings: list[str] = []
    submission = _strip_story_percent_drift(args, deps, warnings)
    submission = _trim_unaudited_market_gaps(submission, deps, warnings)
    submission = _canonicalise_market_gaps(submission, deps, warnings)
    return NormalisedSubmission(submission=submission, warnings=warnings)


def note_copy_repair_state(report: ValidationReport, deps: AgentDeps) -> int:
    if report.ok or report.hard_issues:
        deps.submission.copy_issue_signature = None
        deps.submission.copy_issue_repeats = 0
        deps.submission.copy_repair_blocked = False
        return 0
    signature = tuple(sorted(f"{issue.code}:{issue.message}" for issue in report.issues))
    if deps.submission.copy_issue_signature == signature:
        deps.submission.copy_issue_repeats += 1
    else:
        deps.submission.copy_issue_signature = signature
        deps.submission.copy_issue_repeats = 1
    if deps.submission.copy_issue_repeats >= 3:
        deps.submission.copy_repair_blocked = True
    return deps.submission.copy_issue_repeats


def note_validation_issues(report: ValidationReport, deps: AgentDeps) -> None:
    for issue in report.issues:
        deps.submission.validation_issue_counts[issue.code] = (
            deps.submission.validation_issue_counts.get(issue.code, 0) + 1
        )


def _strip_story_percent_drift(args: ForecastSubmission, deps: AgentDeps, warnings: list[str]) -> ForecastSubmission:
    preview = published_title_preview(deps, args.artifact_id)
    titles = preview["titles"]
    if not titles or not args.narrative.team_stories:
        return args
    stories = {}
    changed: list[str] = []
    for team, story in args.narrative.team_stories.items():
        published = titles.get(team)
        if published is None:
            stories[team] = story
            continue
        summary = _strip_mismatched_percentages(story.summary, published * 100)
        if summary != story.summary:
            changed.append(team)
            stories[team] = story.model_copy(update={"summary": summary})
        else:
            stories[team] = story
    if not changed:
        return args
    warnings.append("stripped non-published percentages from team story summaries for: " + ", ".join(sorted(changed)))
    return args.model_copy(update={"narrative": args.narrative.model_copy(update={"team_stories": stories})})


def _strip_mismatched_percentages(text: str, published_pp: float) -> str:
    matches = list(_PERCENT.finditer(text))
    if len(matches) == 1:
        value = float(matches[0].group(1))
        if abs(value - published_pp) > _STORY_PERCENT_TOLERANCE_PP:
            return _PERCENT.sub(f"{published_pp:.1f}%", text).strip()

    def replacement(match: re.Match[str]) -> str:
        value = float(match.group(1))
        if abs(value - published_pp) <= _STORY_PERCENT_TOLERANCE_PP:
            return match.group(0)
        return ""

    stripped = _PERCENT.sub(replacement, text)
    stripped = _SPACE_BEFORE_PUNCT.sub(r"\1", stripped)
    stripped = _MULTISPACE.sub(" ", stripped)
    return stripped.strip()


def _trim_unaudited_market_gaps(args: ForecastSubmission, deps: AgentDeps, warnings: list[str]) -> ForecastSubmission:
    if not args.market_gaps:
        return args
    covered = _market_gap_audit_teams(deps, args.artifact_id)
    if covered is None:
        return args
    trimmed = [gap for gap in args.market_gaps if gap.team_id in covered]
    removed = sorted({gap.team_id for gap in args.market_gaps} - covered)
    if not removed:
        return args
    warnings.append("removed market_gaps not covered by the factor_audit market_gap row: " + ", ".join(removed))
    return args.model_copy(update={"market_gaps": trimmed})


def _market_gap_audit_teams(deps: AgentDeps, artifact_id: str) -> set[str] | None:
    audit = factor_audit_section(deps, artifact_id)
    if not isinstance(audit, dict):
        return None
    checks = audit.get("checks")
    if not isinstance(checks, list):
        return None
    covered: set[str] = set()
    saw_market_row = False
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("key") != "market_gap" or check.get("status") not in {"checked", "not_material"}:
            continue
        saw_market_row = True
        teams = check.get("teams")
        if isinstance(teams, list):
            covered.update(str(team) for team in teams)
    return covered if saw_market_row else None


def _canonicalise_market_gaps(
    args: ForecastSubmission,
    deps: AgentDeps,
    warnings: list[str],
) -> ForecastSubmission:
    if not args.market_gaps:
        return args
    anchors = validator_anchors(deps)
    model = anchors.baseline_titles or {}
    market = anchors.market_titles or {}
    forecast = published_title_preview(deps, args.artifact_id)["titles"]
    gaps = []
    omitted: list[str] = []
    for gap in args.market_gaps:
        team = gap.team_id
        if team not in model or team not in market or team not in forecast:
            omitted.append(team)
            continue
        model_market = round((model[team] - market[team]) * 100, 2)
        forecast_market = round((forecast[team] - market[team]) * 100, 2)
        gaps.append(
            gap.model_copy(
                update={
                    "model_prob": model[team],
                    "market_prob": market[team],
                    "forecast_prob": forecast[team],
                    "model_market_gap_pp": model_market,
                    "forecast_market_gap_pp": forecast_market,
                    "gap_pp": abs(model_market),
                }
            )
        )
    if omitted:
        warnings.append(
            "removed market_gaps without complete model, market and forecast anchors: " + ", ".join(omitted)
        )
    return args.model_copy(update={"market_gaps": gaps})
