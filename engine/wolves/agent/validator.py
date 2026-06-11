"""Deterministic submit validator: provenance and coherence are hard; large
moves escalate to a steelman, never to a cap on conclusions."""

from __future__ import annotations

import itertools
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.forecast_artifact import ForecastArtifactError, worlds_from_payload
from wolves.agent.ledger import EvidenceLedger

if TYPE_CHECKING:
    from wolves.graph.artifacts import RunArtifactStore

EM_DASH = "—"
_REACH_ORDER = ["r32", "r16", "qf", "sf", "final", "champion"]
_R32_SLOT_COUNT = 16
_UNPRICED_DELTA_FLOOR = 0.5


class ValidatorLimits(BaseModel):
    escalation_threshold_pp: float = 2.0
    escalation_reference_p: float = 0.10
    justification_threshold_pp: float = 1.0


class ValidationIssue(BaseModel):
    code: str
    message: str


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)

    def summary(self) -> str:
        return "; ".join(f"[{i.code}] {i.message}" for i in self.issues)


def validate_submission(
    submission: ForecastSubmission,
    *,
    artifacts: RunArtifactStore | None,
    ledger: EvidenceLedger,
    limits: ValidatorLimits,
    baseline_titles: dict[str, float] | None = None,
    previous_titles: dict[str, float] | None = None,
    focus_team: str | None = None,
) -> ValidationReport:
    """Provenance (computed artifact, no pinned scorelines, weights cohere),
    citation discipline on weights, Paleka coherence on the artifact's own
    numbers, and the escalation diff against the frozen baseline and the
    previous published forecast."""
    issues: list[ValidationIssue] = []
    escalations: list[str] = []
    payload = _artifact_payload(submission, artifacts, issues)
    if payload is not None:
        issues += _check_coherence(payload)
        issues += _check_evidence_priced(submission, payload, ledger)
        if baseline_titles is not None:
            escalations += _diff_escalations(payload, baseline_titles, limits, against="baseline")
        if previous_titles is not None and not (
            submission.change_justification.strip() or submission.inconsistency_note.strip()
        ):
            moved = _diff_escalations(payload, previous_titles, limits, against="previous published forecast")
            if moved:
                issues.append(
                    _issue(
                        "unexplained_drift",
                        "moves beyond threshold vs the previous published forecast need change_justification "
                        f"or an inconsistency_note: {'; '.join(moved)}",
                    )
                )
    issues += _check_weights(submission, ledger)
    issues += _check_narrative(submission)
    issues += _check_em_dashes(submission)
    issues += _check_british_english(submission)
    issues += _check_focus_story(submission, focus_team)
    return ValidationReport(ok=not issues, issues=issues, escalations=escalations)


def _issue(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message)


def _artifact_payload(
    submission: ForecastSubmission, artifacts: RunArtifactStore | None, issues: list[ValidationIssue]
) -> dict | None:
    if artifacts is None:
        issues.append(_issue("no_artifact_store", "this run cannot resolve artifact references"))
        return None
    artifact = artifacts.get(submission.artifact_id)
    if artifact is None:
        issues.append(
            _issue(
                "unknown_artifact",
                f"artifact {submission.artifact_id!r} does not exist; the forecast publishes by reference "
                "to a computed artifact, never typed probabilities",
            )
        )
        return None
    if artifact.kind not in ("mixture", "forecast"):
        issues.append(
            _issue("wrong_artifact_kind", f"artifact {artifact.id} is {artifact.kind}, not a computed forecast")
        )
        return None
    try:
        worlds_from_payload(artifact.payload)
    except ForecastArtifactError as exc:
        issues.append(_issue("artifact_unpublishable", str(exc)))
        return None
    return artifact.payload


def _check_coherence(payload: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    mixture: dict[str, float] = payload.get("mixture") or {}
    for team, p in mixture.items():
        if not 0.0 <= p <= 1.0:
            issues.append(_issue("prob_out_of_range", f"title probability for {team} is {p}"))
    if mixture:
        total = sum(mixture.values())
        if not 0.97 <= total <= 1.03:
            issues.append(_issue("partition_incoherent", f"title probabilities sum to {total:.3f}, not 1"))
    reach: dict[str, float] = payload.get("focus_reach") or {}
    chain = [reach[s] for s in _REACH_ORDER if s in reach]
    if any(later > earlier + 1e-9 for earlier, later in itertools.pairwise(chain)):
        issues.append(_issue("probs_incoherent", "reach probabilities must not increase through rounds"))
    return issues


def _check_evidence_priced(
    submission: ForecastSubmission, payload: dict, ledger: EvidenceLedger
) -> list[ValidationIssue]:
    """An unperturbed baseline cannot publish over material evidence in
    silence: the run either prices the evidence into a computed mixture or
    states why it moves nothing."""
    worlds: dict[str, dict] = payload.get("worlds") or {}
    if worlds and any(spec.get("perturbations") for spec in worlds.values()):
        return []
    material = [
        e.id
        for e in ledger.all()
        if e.status in ("confirmed", "probable") and abs(e.proposed_delta) >= _UNPRICED_DELTA_FLOOR
    ]
    if not material:
        return []
    if submission.change_justification.strip() or submission.inconsistency_note.strip():
        return []
    return [
        _issue(
            "evidence_unpriced",
            f"the artifact is the unperturbed baseline while ledger entries {', '.join(material[:6])} propose "
            "material deltas; cite a computed mixture that prices them (wq.scenario_mixture), or explain in "
            "change_justification why today's evidence moves nothing",
        )
    ]


def _diff_escalations(
    payload: dict, reference: dict[str, float], limits: ValidatorLimits, *, against: str
) -> list[str]:
    mixture: dict[str, float] = payload.get("mixture") or {}
    flagged: list[str] = []
    for team, p in mixture.items():
        anchor = reference.get(team)
        if anchor is None:
            continue
        scale = min(1.0, anchor / limits.escalation_reference_p) if limits.escalation_reference_p > 0 else 1.0
        threshold = limits.escalation_threshold_pp * max(scale, 0.05)
        delta_pp = (p - anchor) * 100
        if abs(delta_pp) > threshold:
            flagged.append(f"{team} {delta_pp:+.2f}pp vs {against} (threshold {threshold:.2f}pp)")
    return flagged


def _check_weights(submission: ForecastSubmission, ledger: EvidenceLedger) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if submission.scenario_weights:
        total = sum(w.weight for w in submission.scenario_weights)
        if not 0.99 <= total <= 1.01:
            issues.append(_issue("weights_incoherent", f"scenario weights sum to {total:.3f}, not 1"))
    for weight in submission.scenario_weights:
        for ledger_id in weight.ledger_ids:
            entry = ledger.get(ledger_id)
            if entry is None:
                issues.append(_issue("unknown_ledger_id", f"weight {weight.name!r} cites unknown id {ledger_id!r}"))
            elif entry.status == "rumour":
                issues.append(
                    _issue("rumour_cited", f"weight {weight.name!r} cites rumour {ledger_id}; rumours justify nothing")
                )
    for ledger_id in submission.evidence_ids:
        if ledger.get(ledger_id) is None:
            issues.append(_issue("unknown_ledger_id", f"evidence_ids cites unknown id {ledger_id!r}"))
    return issues


def _check_narrative(submission: ForecastSubmission) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    narrative = submission.narrative
    if not narrative.focus_story.strip():
        issues.append(_issue("narrative_missing", "the focus team daily story is required"))
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


def _check_em_dashes(submission: ForecastSubmission) -> list[ValidationIssue]:
    if EM_DASH in submission.model_dump_json():
        return [_issue("em_dash", "em-dashes are not allowed anywhere in the submission")]
    return []


# High-frequency Americanisms only: the published copy is British English and
# these are the spellings models actually produce in football narrative.
_AMERICANISMS = re.compile(
    r"\b(favorable|favorite[sd]?|color(s|ed|ful)?|center(s|ed)?|defense[s]?|offense[s]?|"
    r"organiz\w+|analyz\w+|capitaliz\w+|honor(s|ed)?|behavior[s]?|soccer)\b",
    re.IGNORECASE,
)


def _check_focus_story(submission: ForecastSubmission, focus_team: str | None) -> list[ValidationIssue]:
    if focus_team is None:
        return []
    display = focus_team.replace("-", " ").lower()
    if display not in submission.narrative.focus_story.lower():
        return [
            _issue(
                "focus_story_off_topic",
                f"focus_story is the {display} daily story and must concern that team",
            )
        ]
    return []


def _check_british_english(submission: ForecastSubmission) -> list[ValidationIssue]:
    found = sorted({m.group(0).lower() for m in _AMERICANISMS.finditer(submission.model_dump_json())})
    if found:
        return [_issue("american_spelling", f"use British English; replace: {', '.join(found)}")]
    return []
