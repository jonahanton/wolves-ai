"""Deterministic submit validator: provenance and coherence are hard; copy
issues are repair prompts that never cost a retry; large moves escalate to a
steelman, never to a cap on conclusions."""

from __future__ import annotations

import itertools
import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.forecast_artifact import ForecastArtifactError, worlds_from_payload
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.mixture_hygiene import describe_signature, diluted_group_details

if TYPE_CHECKING:
    from wolves.graph.artifacts import RunArtifactStore

EM_DASH = "\u2014"
_REACH_ORDER = ["r32", "r16", "qf", "sf", "final", "champion"]
_UNPRICED_DELTA_FLOOR = 0.5
_BASE_WORLDS = frozenset({"baseline", "model_base", "market_base"})
_FACTOR_AUDIT_WORLD_WEIGHT = 0.15
_VALID_AUDIT_STATUSES = {"checked", "not_material", "not_applicable", "missing"}


class ValidatorLimits(BaseModel):
    escalation_threshold_pp: float = 2.0
    escalation_reference_p: float = 0.10
    justification_threshold_pp: float = 1.0
    weight_dilution_min_combined: float = 0.25
    story_team_count: int = 8


IssueSeverity = Literal["hard", "copy"]


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: IssueSeverity = "hard"


class EscalationDetail(BaseModel):
    team: str
    delta_pp: float
    threshold_pp: float
    against: str

    def summary(self) -> str:
        return f"{self.team} {self.delta_pp:+.2f}pp vs {self.against} (threshold {self.threshold_pp:.2f}pp)"


class ValidationReport(BaseModel):
    ok: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    escalation_details: list[EscalationDetail] = Field(default_factory=list)

    @property
    def hard_issues(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "hard"]

    def summary(self) -> str:
        return "; ".join(f"[{i.code}] {i.message}" for i in self.issues)


UNDERDISPERSED_VS_FLOOR = 1.05
COPY_GUARD_VERSION = 3


def validate_submission(
    submission: ForecastSubmission,
    *,
    artifacts: RunArtifactStore | None,
    ledger: EvidenceLedger,
    limits: ValidatorLimits,
    baseline_titles: dict[str, float] | None = None,
    previous_titles: dict[str, float] | None = None,
    market_titles: dict[str, float] | None = None,
    published_titles: dict[str, float] | None = None,
    focus_vs_floor: float | None = None,
) -> ValidationReport:
    """Provenance (computed artifact, no pinned scorelines, weights cohere),
    citation discipline on weights, Paleka coherence on the artifact's own
    numbers, and the escalation diff against the frozen baseline, the
    previous published forecast and the de-vigged market."""
    issues: list[ValidationIssue] = []
    escalations: list[str] = []
    escalation_details: list[EscalationDetail] = []
    payload = _artifact_payload(submission, artifacts, issues)
    titles: dict[str, float] = {}
    if payload is not None:
        titles = published_titles or payload.get("mixture") or {}
        issues += _check_coherence(payload)
        issues += _check_evidence_priced(submission, payload, ledger)
        issues += _check_weight_dilution(payload, limits)
        issues += _check_team_stories(
            submission,
            titles,
            limits,
            visible_bucket_count=_visible_distribution_bucket_count(submission, payload),
        )
        issues += _check_scenario_metadata(submission, payload)
        issues += _check_factor_audit(submission, payload, has_previous_context=previous_titles is not None)
        issues += _check_market_gap_contract(submission, titles=titles, market_titles=market_titles)
        if baseline_titles is not None:
            details = _diff_escalation_details(titles, baseline_titles, limits, against="baseline")
            escalation_details += details
            escalations += [detail.summary() for detail in details]
        if previous_titles is not None and not (
            submission.change_justification.strip() or submission.inconsistency_note.strip()
        ):
            moved = _diff_escalations(
                titles,
                previous_titles,
                limits,
                against="previous published forecast",
                min_threshold_pp=limits.justification_threshold_pp,
            )
            if moved:
                issues.append(
                    _issue(
                        "unexplained_drift",
                        "moves beyond threshold vs the previous published forecast need a team-level reason in "
                        "change_justification, or an inconsistency_note if the move is mechanical or not meaningful: "
                        f"{'; '.join(moved)}",
                    )
                )
        issues += _check_audit_consistency(payload)
        if market_titles is not None:
            gaps = _diff_escalations(
                titles,
                market_titles,
                limits,
                against="de-vigged market",
                min_threshold_pp=limits.justification_threshold_pp,
            )
            justification = submission.market_justification.lower()
            # Per-team coverage: a justification that argues England cannot
            # silently carry an unexamined Germany gap.
            unargued = [
                g
                for g in gaps
                if g.split()[0] not in justification and g.split()[0].replace("-", " ") not in justification
            ]
            if unargued:
                issues.append(
                    _issue(
                        "market_unreconciled",
                        "the mixture publishes unblended, so every gap beyond threshold vs the de-vigged market "
                        f"needs market_justification naming that team and its computation: {'; '.join(unargued)}",
                    )
                )
    issues += _check_weights(submission, ledger)
    issues += _check_em_dashes(submission)
    issues += _check_british_english(submission)
    issues += _check_headline(submission, titles)
    issues += _check_public_copy_claims(submission)
    issues += _check_mixture_dispersion(submission, ledger, focus_vs_floor)
    issues += _check_news_impacts(submission, artifacts)
    return ValidationReport(
        ok=not issues,
        issues=issues,
        escalations=escalations,
        escalation_details=escalation_details,
    )


def _check_mixture_dispersion(
    submission: ForecastSubmission, ledger: EvidenceLedger, focus_vs_floor: float | None
) -> list[ValidationIssue]:
    """Copy-severity nudge only: hard width enforcement would teach fake width."""
    if focus_vs_floor is None or focus_vs_floor >= UNDERDISPERSED_VS_FLOOR:
        return []
    if submission.change_justification.strip():
        return []
    material = [e for e in ledger.all() if e.status in ("confirmed", "probable")]
    if not material:
        return []
    return [
        _copy_issue(
            "mixture_underdispersed",
            f"the cited mixture's focus-team band is {focus_vs_floor}x the parameter-noise floor while the "
            "ledger holds material evidence; widen via a world you believe in, or say in "
            "change_justification why the evidence resolves nothing",
        )
    ]


_STORY_SUMMARY_MAX = 200
_STORY_WHY_MAX = 480
_STORY_PERCENT_TOLERANCE_PP = 0.15
_PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
_ORDINAL_RANKS = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
    "sixth": 6,
    "6th": 6,
    "seventh": 7,
    "7th": 7,
    "eighth": 8,
    "8th": 8,
    "ninth": 9,
    "9th": 9,
    "tenth": 10,
    "10th": 10,
    "eleventh": 11,
    "11th": 11,
    "twelfth": 12,
    "12th": 12,
}
_ORDINAL_PATTERN = "|".join(re.escape(word) for word in sorted(_ORDINAL_RANKS, key=len, reverse=True))


def _check_team_stories(
    submission: ForecastSubmission,
    titles: dict[str, float],
    limits: ValidatorLimits,
    *,
    visible_bucket_count: int | None = None,
) -> list[ValidationIssue]:
    """Copy-severity: once the agent writes stories, cover the mixture leaders, jargon-free, in length."""
    stories = submission.narrative.team_stories
    if not stories:
        return []
    issues: list[ValidationIssue] = []
    leaders = [t for t, _ in sorted(titles.items(), key=lambda kv: -kv[1])[: limits.story_team_count]]
    missing = [t for t in leaders if t not in stories]
    if missing:
        issues.append(
            _copy_issue(
                "team_stories_missing",
                f"write a team_stories entry for each leader of your own mixture: missing {', '.join(missing[:6])}",
            )
        )
    for team, story in stories.items():
        jargon = sorted({m.group(0).lower() for m in _STORY_INTERNAL_COPY.finditer(f"{story.summary} {story.why}")})
        if jargon:
            issues.append(
                _copy_issue(
                    "team_story_jargon", f"team_stories[{team}] is plain English; rephrase: {', '.join(jargon)}"
                )
            )
        if len(story.summary) > _STORY_SUMMARY_MAX or len(story.why) > _STORY_WHY_MAX:
            issues.append(
                _copy_issue("team_story_too_long", f"team_stories[{team}] is over length; tighten the entry")
            )
        if team in titles:
            published_pp = titles[team] * 100
            mismatched = [
                value
                for value in (float(match.group(1)) for match in _PERCENT.finditer(story.summary))
                if abs(value - published_pp) > _STORY_PERCENT_TOLERANCE_PP
            ]
            if mismatched:
                issues.append(
                    _copy_issue(
                        "team_story_probability_mismatch",
                        f"team_stories[{team}] summary says {mismatched[0]:.1f}% but the published title "
                        f"probability is {published_pp:.1f}%; quote the published preview or remove the number",
                    )
                )
        issues += _rank_copy_issues(
            f"team_stories[{team}]",
            f"{story.summary} {story.why}",
            titles,
            only_team=team,
        )
        issues += _visible_bucket_count_issues(
            f"team_stories[{team}]",
            f"{story.summary} {story.why}",
            visible_bucket_count,
            visible_label="camps" if submission.camps else "worlds",
        )
    return issues


_COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_COUNT_PATTERN = "|".join(str(n) for n in range(1, 11)) + "|" + "|".join(_COUNT_WORDS)
_BUCKET_COUNT_CLAIM = re.compile(
    rf"\b(?:all\s+)?(?P<count>{_COUNT_PATTERN})\s+(?P<label>worlds|camps)\b",
    re.IGNORECASE,
)


def _visible_distribution_bucket_count(submission: ForecastSubmission, payload: dict) -> int | None:
    if submission.camps:
        return len(submission.camps)
    worlds = payload.get("worlds") or {}
    return len(worlds) or None


def _visible_bucket_count_issues(
    field: str, text: str, visible_count: int | None, *, visible_label: str
) -> list[ValidationIssue]:
    if visible_count is None:
        return []
    issues: list[ValidationIssue] = []
    for match in _BUCKET_COUNT_CLAIM.finditer(text):
        count = _count_value(match.group("count"))
        if count == visible_count:
            continue
        issues.append(
            _copy_issue(
                "team_story_bucket_count_mismatch",
                f"{field} says {match.group(0)!r}, but the public distribution shows "
                f"{visible_count} {visible_label}; count the visible buckets or remove the count",
            )
        )
    return issues


def _count_value(value: str) -> int:
    lowered = value.lower()
    if lowered.isdigit():
        return int(lowered)
    return _COUNT_WORDS[lowered]


def _rank_copy_issues(
    field: str, text: str, titles: dict[str, float], *, only_team: str | None = None
) -> list[ValidationIssue]:
    if not titles:
        return []
    ranks = {
        team: rank
        for rank, (team, _) in enumerate(sorted(titles.items(), key=lambda kv: (-kv[1], kv[0])), start=1)
    }
    teams = [only_team] if only_team is not None and only_team in ranks else list(ranks)
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, int]] = set()
    for team in teams:
        aliases = _team_rank_aliases(team)
        for alias in aliases:
            for claimed, word in _rank_claims_for_alias(text, alias):
                if claimed == ranks[team] or (team, claimed) in seen:
                    continue
                seen.add((team, claimed))
                issues.append(
                    _copy_issue(
                        "rank_claim_mismatch",
                        f"{field} says {team} are {word} but the published title rank is "
                        f"{_ordinal(ranks[team])}; use published_preview.ranking or remove rank wording",
                    )
                )
    return issues


def _rank_claims_for_alias(text: str, alias: str) -> list[tuple[int, str]]:
    escaped = re.escape(alias)
    before = re.compile(
        rf"\b{escaped}\b\s+(?:are|is|sit|sits|rank|ranks|ranked|rate|rates|rated|place|places|placed)"
        rf"(?:\s+as)?\s+(?:joint[-\s])?\b({_ORDINAL_PATTERN})\b(?!-)",
        re.I,
    )
    after = re.compile(
        rf"\b({_ORDINAL_PATTERN})\b(?!-)(?:[-\s]+(?:placed|ranked|rated))?\s+\b{escaped}\b",
        re.I,
    )
    claims: list[tuple[int, str]] = []
    for pattern in (before, after):
        for match in pattern.finditer(text):
            word = match.group(1).lower()
            claims.append((_ORDINAL_RANKS[word], word))
    return claims


def _team_rank_aliases(team: str) -> set[str]:
    spaced = team.replace("-", " ")
    aliases = {team, spaced}
    if " and " in spaced:
        aliases.add(spaced.replace(" and ", " & "))
    if team == "usa":
        aliases.add("us")
    return aliases


def _ordinal(rank: int) -> str:
    suffix = "th" if 10 <= rank % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(rank % 10, "th")
    return f"{rank}{suffix}"


def _check_news_impacts(
    submission: ForecastSubmission, artifacts: RunArtifactStore | None
) -> list[ValidationIssue]:
    """Copy-severity: every material priced item should carry a why in news_impacts."""
    if artifacts is None:
        return []
    material_by_ledger: dict[str, bool] = {}
    for record in artifacts.all():
        if record.kind != "quant":
            continue
        artifact = artifacts.get(record.id)
        if artifact is None:
            continue
        for raw in artifact.payload.get("priced_items") or []:
            ledger_id = raw.get("ledger_id")
            if ledger_id:
                material_by_ledger[str(ledger_id)] = bool(raw.get("material"))
    material = {ledger_id for ledger_id, is_material in material_by_ledger.items() if is_material}
    missing = sorted(ledger_id for ledger_id in material if not submission.news_impacts.get(ledger_id, "").strip())
    if not missing:
        return []
    return [
        _copy_issue(
            "news_impact_missing",
            f"write a one-sentence news_impacts entry for each material priced item: missing {', '.join(missing[:6])}",
        )
    ]


def _check_weight_dilution(payload: dict, limits: ValidatorLimits) -> list[ValidationIssue]:
    """Near-duplicate worlds split a vote and bias the mix."""
    weights: dict[str, float] = payload.get("weights") or {}
    worlds_block: dict[str, dict] = payload.get("worlds") or {}
    worlds = {
        name: (weights.get(name, 0.0), worlds_block[name].get("perturbations", []))
        for name in worlds_block
        if name not in _BASE_WORLDS
    }
    diluted = diluted_group_details(worlds, min_combined_weight=limits.weight_dilution_min_combined)
    if not diluted:
        return []
    described = "; ".join(
        f"{' and '.join(group.names)} ({group.combined_weight:g} combined; shared footprint: "
        f"{describe_signature(group.signature)})"
        for group in diluted
    )
    return [
        _issue(
            "weight_dilution",
            "these worlds share a directional perturbation footprint, so the artifact may count one stance "
            "more than once. This is an artifact structure issue, not a copy edit: submit another valid "
            f"artifact or ask master to brief quant for a corrected mixture. Details: {described}",
        )
    ]


_KILLED_BRANCH_STATUSES = {"below_floor", "collapsed", "rejected"}
_BRANCH_SURVIVAL_MIN_WEIGHT = 1e-6


def _check_audit_consistency(payload: dict) -> list[ValidationIssue]:
    """A branch the artifact's own branch_audit killed cannot keep a weighted world."""
    audit = payload.get("branch_audit")
    if not isinstance(audit, dict):
        return []
    checks = audit.get("checks")
    if not isinstance(checks, list):
        return []
    weights: dict[str, float] = payload.get("weights") or {}
    contradictions: list[str] = []
    for check in checks:
        if not isinstance(check, dict) or str(check.get("status")) not in _KILLED_BRANCH_STATUSES:
            continue
        world_names = check.get("world_names")
        if not isinstance(world_names, list):
            continue
        survivors = sorted(
            str(name)
            for name in world_names
            if str(name) not in _BASE_WORLDS and weights.get(str(name), 0.0) > _BRANCH_SURVIVAL_MIN_WEIGHT
        )
        if survivors:
            contradictions.append(
                f"{check.get('key')} ({check.get('status')}) still weights {', '.join(survivors)}"
            )
    if not contradictions:
        return []
    return [
        _issue(
            "branch_audit_self_inconsistent",
            "the mixture publishes worlds its own branch_audit killed; a branch priced below floor, collapsed or "
            "rejected cannot keep a weighted standalone world. Drop the world or have quant re-audit the branch: "
            + "; ".join(contradictions),
        )
    ]


def _check_scenario_metadata(submission: ForecastSubmission, payload: dict) -> list[ValidationIssue]:
    weights: dict[str, float] = payload.get("weights") or {}
    worlds_block: dict[str, dict] = payload.get("worlds") or {}
    if not worlds_block:
        return []
    issues: list[ValidationIssue] = []
    submitted = {w.name: w for w in submission.scenario_weights}
    if len(weights) > 1 and not submitted:
        return [
            _issue(
                "scenario_weights_missing",
                "multi-world artifacts need scenario_weights matching the artifact's world names and weights",
            )
        ]
    missing = set(weights) - set(submitted)
    extra = set(submitted) - set(weights)
    mismatched = [
        name for name, weight in weights.items() if name in submitted and abs(submitted[name].weight - weight) > 1e-6
    ]
    if missing or extra or mismatched:
        detail = []
        if missing:
            detail.append(f"missing {', '.join(sorted(missing))}")
        if extra:
            detail.append(f"unexpected {', '.join(sorted(extra))}")
        if mismatched:
            detail.append(f"wrong weight for {', '.join(sorted(mismatched))}")
        issues.append(
            _issue(
                "scenario_weights_mismatch",
                "scenario_weights must match the submitted artifact's world names and weights: "
                + "; ".join(detail),
            )
        )
    issues += _check_camps(submission)
    return issues


def _check_factor_audit(
    submission: ForecastSubmission, payload: dict, *, has_previous_context: bool
) -> list[ValidationIssue]:
    weights: dict[str, float] = payload.get("weights") or {}
    worlds: dict[str, dict] = payload.get("worlds") or {}
    if not weights or not worlds:
        return []
    if "conditionals" not in payload and "noise_floor_pp" not in payload:
        return []
    audit = payload.get("factor_audit")
    non_base_mass = sum(weight for name, weight in weights.items() if name not in _BASE_WORLDS)
    large_non_base = non_base_mass >= _FACTOR_AUDIT_WORLD_WEIGHT
    has_market_stance = bool(submission.market_justification.strip() or submission.market_gaps)
    if audit is None:
        if large_non_base or has_market_stance:
            reason = f"non-base mass {non_base_mass:.2f}" if large_non_base else "market stance"
            return [
                _issue(
                    "factor_audit_missing",
                    "the submitted mixture needs a factor_audit for consequential non-base worlds or market "
                    f"stances: {reason}",
                )
            ]
        return []
    checks = audit.get("checks") if isinstance(audit, dict) else None
    if not isinstance(checks, list):
        return [_issue("factor_audit_malformed", "factor_audit.checks must be a list of coverage checks")]
    by_key = {
        str(check.get("key")): str(check.get("status"))
        for check in checks
        if isinstance(check, dict) and check.get("key")
    }
    issues: list[ValidationIssue] = []
    invalid = sorted(
        {
            str(check.get("key"))
            for check in checks
            if isinstance(check, dict) and str(check.get("status")) not in _VALID_AUDIT_STATUSES
        }
    )
    if invalid:
        issues.append(_issue("factor_audit_malformed", f"factor_audit has invalid statuses for: {', '.join(invalid)}"))
    empty_summary = sorted(
        {
            str(check.get("key"))
            for check in checks
            if isinstance(check, dict) and not str(check.get("summary") or "").strip()
        }
    )
    if empty_summary:
        issues.append(
            _issue("factor_audit_malformed", f"factor_audit rows need summaries: {', '.join(empty_summary)}")
        )
    required = _required_factor_audit_keys(
        submission,
        payload,
        large_non_base=large_non_base,
        has_market_stance=has_market_stance,
        has_previous_context=has_previous_context,
    )
    absent = sorted(key for key in required if key not in by_key)
    if absent:
        issues.append(
            _issue(
                "factor_audit_missing_coverage",
                f"factor_audit omits critical coverage rows: {', '.join(absent)}",
            )
        )
    missing = sorted(key for key in required if by_key.get(key) == "missing")
    if missing:
        issues.append(
            _issue(
                "factor_audit_missing_coverage",
                f"factor_audit leaves critical coverage missing: {', '.join(missing)}",
            )
        )
    if has_market_stance and by_key.get("market_gap") not in {"checked", "not_material"}:
        issues.append(
            _issue(
                "market_audit_missing",
                "a submitted market stance needs a factor_audit check keyed market_gap with status checked or "
                "not_material",
            )
        )
    if submission.market_gaps:
        market_rows = [
            check
            for check in checks
            if isinstance(check, dict)
            and str(check.get("key")) == "market_gap"
            and str(check.get("status")) in {"checked", "not_material"}
        ]
        covered: set[str] = set()
        for check in market_rows:
            teams = check.get("teams")
            if isinstance(teams, list):
                covered.update(str(team) for team in teams)
        missing_teams = sorted({gap.team_id for gap in submission.market_gaps} - covered)
        if missing_teams:
            issues.append(
                _issue(
                    "market_audit_missing_team",
                    "the market_gap audit row must name every submitted market-gap team it checked: "
                    + ", ".join(missing_teams),
                )
            )
    if large_non_base and "mixture_spread" not in by_key:
        issues.append(
            _copy_issue(
                "factor_audit_spread_missing",
                "large non-base worlds should record a mixture_spread audit row, or say why spread was not applicable",
            )
        )
    return issues


def _required_factor_audit_keys(
    submission: ForecastSubmission,
    payload: dict,
    *,
    large_non_base: bool,
    has_market_stance: bool,
    has_previous_context: bool,
) -> set[str]:
    if not large_non_base and not has_market_stance:
        return set()
    weights: dict[str, float] = payload.get("weights") or {}
    required = {"mixture_spread"} if large_non_base else set()
    if has_previous_context:
        required.add("previous_continuity")
    if {"model_base", "market_base"} <= set(weights):
        required.add("bases")
    if has_market_stance:
        required.add("market_gap")
    if payload.get("priced_items") or submission.news_impacts:
        required.add("ledger_pricing")
    return required


_MARKET_GAP_TOLERANCE_PP = 0.2


def _check_market_gap_contract(
    submission: ForecastSubmission,
    *,
    titles: dict[str, float],
    market_titles: dict[str, float] | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[str, int] = {}
    for gap in submission.market_gaps:
        seen[gap.team_id] = seen.get(gap.team_id, 0) + 1
        # gap_pp is fully derived from the two validated components, so correct
        # it in place rather than burn a re-forecast on a mistyped derived field.
        gap.gap_pp = round(abs((gap.market_prob - gap.model_prob) * 100), 2)
        if gap.floor_multiple is not None and gap.floor_multiple < 0:
            issues.append(
                _issue("market_gap_malformed", f"market_gaps[{gap.team_id}] floor_multiple must be positive")
            )
        published = titles.get(gap.team_id)
        if published is not None and abs(gap.model_prob - published) * 100 > _MARKET_GAP_TOLERANCE_PP:
            issues.append(
                _issue(
                    "market_gap_malformed",
                    f"market_gaps[{gap.team_id}] model_prob is {gap.model_prob:.4f}, but the published "
                    f"title probability is {published:.4f}",
                )
            )
        market = market_titles.get(gap.team_id) if market_titles is not None else None
        if market is not None and abs(gap.market_prob - market) * 100 > _MARKET_GAP_TOLERANCE_PP:
            issues.append(
                _issue(
                    "market_gap_malformed",
                    f"market_gaps[{gap.team_id}] market_prob is {gap.market_prob:.4f}, but the de-vigged market "
                    f"anchor is {market:.4f}",
                )
            )
    duplicates = sorted(team for team, count in seen.items() if count > 1)
    if duplicates:
        issues.append(_issue("market_gap_duplicate", "market_gaps repeats teams: " + ", ".join(duplicates)))
    return issues


def _check_camps(submission: ForecastSubmission) -> list[ValidationIssue]:
    if not submission.scenario_weights and not submission.camps:
        return []
    issues: list[ValidationIssue] = []
    declared: dict[str, int] = {}
    for camp in submission.camps:
        declared[camp.key] = declared.get(camp.key, 0) + 1
    duplicates = sorted(key for key, count in declared.items() if count > 1)
    if duplicates:
        issues.append(_copy_issue("camp_duplicate", f"declare each camp once: {', '.join(duplicates)}"))
    used = {w.camp for w in submission.scenario_weights if w.camp}
    missing = sorted(used - set(declared))
    if missing:
        issues.append(_copy_issue("camp_missing", f"declare each used camp key: {', '.join(missing)}"))
    orphaned = sorted(set(declared) - used)
    if orphaned:
        issues.append(
            _copy_issue("camp_orphaned", f"remove declared camps with no member worlds: {', '.join(orphaned)}")
        )
    blank = sorted(c.key for c in submission.camps if not c.label.strip() or not c.summary.strip())
    if blank:
        issues.append(_copy_issue("camp_copy_missing", f"each camp needs a label and summary: {', '.join(blank)}"))
    return issues


def _issue(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message)


def _copy_issue(code: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, severity="copy")


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
    # The two standing base worlds express priors, not today's evidence.
    if any(spec.get("perturbations") for name, spec in worlds.items() if name not in _BASE_WORLDS):
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
    titles: dict[str, float],
    reference: dict[str, float],
    limits: ValidatorLimits,
    *,
    against: str,
    min_threshold_pp: float = 0.0,
) -> list[str]:
    return [
        detail.summary()
        for detail in _diff_escalation_details(
            titles,
            reference,
            limits,
            against=against,
            min_threshold_pp=min_threshold_pp,
        )
    ]


def _diff_escalation_details(
    titles: dict[str, float],
    reference: dict[str, float],
    limits: ValidatorLimits,
    *,
    against: str,
    min_threshold_pp: float = 0.0,
) -> list[EscalationDetail]:
    flagged: list[EscalationDetail] = []
    for team, p in titles.items():
        anchor = reference.get(team)
        if anchor is None:
            continue
        scale = min(1.0, anchor / limits.escalation_reference_p) if limits.escalation_reference_p > 0 else 1.0
        threshold = max(limits.escalation_threshold_pp * max(scale, 0.05), min_threshold_pp)
        delta_pp = (p - anchor) * 100
        if abs(delta_pp) > threshold:
            flagged.append(
                EscalationDetail(
                    team=team,
                    delta_pp=round(delta_pp, 4),
                    threshold_pp=round(threshold, 4),
                    against=against,
                )
            )
    return flagged


def _check_weights(submission: ForecastSubmission, ledger: EvidenceLedger) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if submission.scenario_weights:
        total = sum(w.weight for w in submission.scenario_weights)
        if not 0.99 <= total <= 1.01:
            issues.append(_issue("weights_incoherent", f"scenario weights sum to {total:.3f}, not 1"))
    for weight in submission.scenario_weights:
        if not weight.rationale.strip():
            issues.append(_issue("weight_unargued", f"scenario weight {weight.name!r} needs a one-line rationale"))
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


def _check_em_dashes(submission: ForecastSubmission) -> list[ValidationIssue]:
    if EM_DASH in submission.model_dump_json():
        return [_copy_issue("em_dash", "em-dashes are not allowed anywhere in the submission")]
    return []


# High-frequency Americanisms only: the published copy is British English and
# these are the spellings models actually produce in football narrative.
_AMERICANISMS = re.compile(
    r"\b(favorable|favorite[sd]?|color(s|ed|ful)?|center(s|ed)?|defense[s]?|offense[s]?|"
    r"organiz\w+|analyz\w+|capitaliz\w+|honor(s|ed)?|behavior[s]?|soccer)\b",
    re.IGNORECASE,
)


# The soft target is ~420 chars over the 54ch lede; the grace band absorbs a
# marginal overshoot rather than burning a turn reformatting prose that reads well.
_HEADLINE_SOFT_CHARS = 420
_HEADLINE_CHAR_GRACE = 180
_HEADLINE_MAX_CHARS = _HEADLINE_SOFT_CHARS + _HEADLINE_CHAR_GRACE
_HEADLINE_JARGON = re.compile(
    r"\b(artifact[s]?|perturbation[s]?|n_sims|sim[s]?\b|escalation[s]?|validator|governor|"
    r"raw mixture|noise floor|factor_audit|branch_audit|quant|"
    r"submit_forecast|check_forecast|ledger[- ]?id[s]?|scenario[-_ ]?id[s]?|run[-_ ]?id[s]?|"
    r"mixture-\d+|led-\d+|scn-\d+|evidence-\d+|retrieval-\d+)\b",
    re.IGNORECASE,
)
_STORY_INTERNAL_COPY = re.compile(
    r"\b(artifact[s]?|n_sims|validator|governor|raw mixture|factor_audit|branch_audit|"
    r"quant|submit_forecast|check_forecast|ledger[- ]?id[s]?|scenario[-_ ]?id[s]?|run[-_ ]?id[s]?|"
    r"mixture-\d+|led-\d+|scn-\d+|evidence-\d+|retrieval-\d+)\b",
    re.IGNORECASE,
)
_HOST_TEAMS = frozenset({"usa", "canada", "mexico"})
_HOST_CLAIM = re.compile(
    r"\b(host(?:s|ed|ing)?|home[- ]?(?:soil|continent|advantage)|local (?:support|crowd|conditions))\b",
    re.IGNORECASE,
)
_MARKET_CAUSAL = re.compile(
    r"\bmarkets?\b.{0,80}\b(reflects?|captures?|endorses?|bakes? in|priced? in|prices? in|is buying|are buying)\b",
    re.IGNORECASE,
)


def _check_headline(submission: ForecastSubmission, titles: dict[str, float]) -> list[ValidationIssue]:
    headline = submission.narrative.headline.strip()
    if not headline:
        return [_issue("headline_missing", "narrative.headline is required: the forecast's reasoning in plain English")]
    issues: list[ValidationIssue] = []
    if len(headline) > _HEADLINE_MAX_CHARS:
        issues.append(_copy_issue("headline_too_long", f"headline must stay under {_HEADLINE_MAX_CHARS} characters"))
    found = sorted({m.group(0).lower() for m in _HEADLINE_JARGON.finditer(headline)})
    if found:
        issues.append(
            _copy_issue(
                "headline_jargon",
                f"the headline is plain English for a reader who has never met the model; rephrase: {', '.join(found)}",
            )
        )
    if titles:
        published_pp = [p * 100 for p in titles.values()]
        mismatched = [
            value
            for value in (float(match.group(1)) for match in _PERCENT.finditer(headline))
            if all(abs(value - published) > _STORY_PERCENT_TOLERANCE_PP for published in published_pp)
        ]
        if mismatched:
            issues.append(
                _copy_issue(
                    "headline_probability_mismatch",
                    f"headline says {mismatched[0]:.1f}% but no published title probability matches; "
                    "quote the published preview or remove the number",
                )
            )
        issues += _rank_copy_issues("headline", headline, titles)
    return issues


def _check_public_copy_claims(submission: ForecastSubmission) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    public_fields = [("headline", submission.narrative.headline)]
    public_fields.extend(
        (f"team_stories[{team}]", f"{story.summary} {story.why}")
        for team, story in submission.narrative.team_stories.items()
    )
    for field, text in public_fields:
        if _MARKET_CAUSAL.search(text):
            issues.append(
                _copy_issue(
                    "market_causal_copy",
                    f"{field} assigns a cause to the market price; rephrase as a model-market disagreement or cite "
                    "the public fact directly",
                )
            )
    for team, story in submission.narrative.team_stories.items():
        if team in _HOST_TEAMS:
            continue
        if _HOST_CLAIM.search(f"{story.summary} {story.why}"):
            issues.append(
                _copy_issue(
                    "host_advantage_copy",
                    f"team_stories[{team}] implies host or home-continent advantage; only USA, Canada and Mexico "
                    "are host teams in this tournament",
                )
            )
    return issues


def _check_british_english(submission: ForecastSubmission) -> list[ValidationIssue]:
    found = sorted({m.group(0).lower() for m in _AMERICANISMS.finditer(submission.model_dump_json())})
    if found:
        return [_copy_issue("american_spelling", f"use British English; replace: {', '.join(found)}")]
    return []
