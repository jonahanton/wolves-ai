"""Deterministic submit validator: the hard boundary on the agent's freedom."""

from __future__ import annotations

import itertools
from datetime import date

from pydantic import BaseModel, Field

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.ledger import EvidenceLedger

EM_DASH = "—"
_REACH_ORDER = ["r32", "r16", "qf", "sf", "final", "champion"]
_R32_SLOT_COUNT = 16


class ValidatorLimits(BaseModel):
    confirmed_delta_cap_elo: float = 50.0
    soft_delta_cap_elo: float = 10.0
    justification_threshold: float = 0.05
    delta_cap_scale: float = 1.0


class ValidationIssue(BaseModel):
    code: str
    message: str


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    def summary(self) -> str:
        return "; ".join(f"[{i.code}] {i.message}" for i in self.issues)


def validate_submission(
    submission: ForecastSubmission,
    *,
    ledger: EvidenceLedger,
    limits: ValidatorLimits,
) -> ValidationReport:
    """Check probability coherence, override caps, ledger citations, fixture
    offset expiries, narrative completeness and justification requirements."""
    issues: list[ValidationIssue] = []
    issues += _check_probabilities(submission)
    issues += _check_overrides(submission, ledger, limits)
    issues += _check_fixture_offsets(submission)
    issues += _check_narrative(submission)
    issues += _check_justifications(submission, limits)
    issues += _check_em_dashes(submission)
    return ValidationReport(ok=not issues, issues=issues)


def _issue(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message)


def _check_probabilities(submission: ForecastSubmission) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    probs = submission.england_reach_probs
    if not probs:
        return [_issue("probs_missing", "england_reach_probs is required")]
    for stage, p in probs.items():
        if not 0.0 <= p <= 1.0:
            issues.append(_issue("prob_out_of_range", f"reach prob for {stage} is {p}"))
    chain = [probs[s] for s in _REACH_ORDER if s in probs]
    if any(later > earlier + 1e-9 for earlier, later in itertools.pairwise(chain)):
        issues.append(_issue("probs_incoherent", "reach probabilities must not increase through rounds"))
    return issues


def _check_overrides(
    submission: ForecastSubmission,
    ledger: EvidenceLedger,
    limits: ValidatorLimits,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    confirmed_cap = limits.confirmed_delta_cap_elo * limits.delta_cap_scale
    soft_cap = limits.soft_delta_cap_elo * limits.delta_cap_scale
    soft_totals: dict[str, float] = {}

    for override in submission.rating_overrides:
        label = f"override for {override.team_id}"
        entries = []
        for ledger_id in override.ledger_ids:
            entry = ledger.get(ledger_id)
            if entry is None:
                issues.append(_issue("unknown_ledger_id", f"{label} cites unknown ledger id {ledger_id!r}"))
            else:
                entries.append(entry)
        if override.delta_elo == 0.0:
            continue
        statuses = {e.status for e in entries}
        if not entries or statuses <= {"rumour"}:
            issues.append(
                _issue(
                    "uncited_delta",
                    f"{label} has nonzero delta without a confirmed or probable ledger citation; rumours get zero",
                )
            )
            continue
        if "confirmed" in statuses:
            if abs(override.delta_elo) > confirmed_cap:
                issues.append(
                    _issue(
                        "confirmed_cap_exceeded",
                        f"{label} delta {override.delta_elo:+.1f} exceeds the {confirmed_cap:.0f} Elo confirmed cap",
                    )
                )
        else:
            soft_totals[override.team_id] = soft_totals.get(override.team_id, 0.0) + abs(override.delta_elo)

    for team_id, total in soft_totals.items():
        if total > soft_cap:
            issues.append(
                _issue(
                    "soft_cap_exceeded",
                    f"soft-evidence deltas for {team_id} total {total:.1f} Elo, above the {soft_cap:.0f} Elo cap",
                )
            )
    return issues


def _check_fixture_offsets(submission: ForecastSubmission) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for offset in submission.fixture_offsets:
        try:
            date.fromisoformat(offset.expiry)
        except ValueError:
            issues.append(
                _issue("offset_expiry_invalid", f"fixture offset for match {offset.match} needs an ISO date expiry")
            )
    return issues


def _check_narrative(submission: ForecastSubmission) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    narrative = submission.narrative
    if not narrative.england_story.strip():
        issues.append(_issue("narrative_missing", "the England daily story is required"))
    if not narrative.travel_memo.strip():
        issues.append(_issue("narrative_missing", "the travel memo is required"))
    rationales = {k: v for k, v in narrative.slot_rationales.items() if v.strip()}
    if len(rationales) != _R32_SLOT_COUNT:
        issues.append(
            _issue(
                "slot_rationales_incomplete",
                f"need one rationale per R32 slot ({_R32_SLOT_COUNT}), got {len(rationales)}",
            )
        )
    return issues


def _check_justifications(submission: ForecastSubmission, limits: ValidatorLimits) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if abs(submission.delta_vs_market) > limits.justification_threshold and not submission.market_justification.strip():
        issues.append(
            _issue("market_justification_missing", "delta_vs_market is above threshold and needs justification text")
        )
    if (
        abs(submission.delta_vs_yesterday) > limits.justification_threshold
        and not submission.change_justification.strip()
    ):
        issues.append(
            _issue("change_justification_missing", "delta_vs_yesterday is above threshold and needs justification text")
        )
    return issues


def _check_em_dashes(submission: ForecastSubmission) -> list[ValidationIssue]:
    if EM_DASH in submission.model_dump_json():
        return [_issue("em_dash", "em-dashes are not allowed anywhere in the submission")]
    return []
