"""Shared validator invocation for the submission tools: resolves the anchor
distributions (frozen baseline, previous published forecast, de-vigged market)
and runs the deterministic validator over a submission. The baseline and
market anchors resolve once per run, cached on the shared SubmissionState."""

from __future__ import annotations

from typing import TypedDict

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps, ValidatorAnchors
from wolves.agent.publish_surface import publish_surface
from wolves.agent.validator import ValidationReport, validate_submission

_BASELINE_SIMS = 50_000
_BASE_WORLDS = {"baseline", "model_base", "market_base"}
_GENERIC_WORLD_NAMES = {"evidence", "model_evidence", "market_evidence", "upside", "downside"}


class PublishedTitlePreview(TypedDict):
    titles: dict[str, float]
    raw_titles: dict[str, float]
    baseline_titles: dict[str, float]
    ranking: list[dict[str, float | int | str]]
    governor_scale: float
    effective_d: float
    active: bool


class MarketGapContract(TypedDict):
    submitted: list[dict[str, object]]
    anchor_gaps: list[dict[str, object]]


def _anchors(deps: AgentDeps) -> ValidatorAnchors:
    if deps.submission.anchors is None:
        deps.submission.anchors = ValidatorAnchors(
            baseline_titles=_baseline_titles(deps), market_titles=_market_titles(deps)
        )
    return deps.submission.anchors


def published_title_preview(deps: AgentDeps, artifact_id: str) -> PublishedTitlePreview:
    """Final title surface a clean submission would publish."""
    surface = publish_surface(deps, artifact_id)
    if surface is None:
        return {
            "titles": {},
            "raw_titles": {},
            "baseline_titles": {},
            "ranking": [],
            "governor_scale": 1.0,
            "effective_d": 1.0,
            "active": False,
        }
    ranking = [
        {"rank": rank, "team": team, "p_title": p_title, "pct": p_title * 100}
        for rank, (team, p_title) in enumerate(
            sorted(surface.published_titles.items(), key=lambda kv: (-kv[1], kv[0])), start=1
        )
    ]
    return {
        "titles": surface.published_titles,
        "raw_titles": surface.raw_titles,
        "baseline_titles": surface.baseline_titles,
        "ranking": ranking,
        "governor_scale": surface.governor_scale,
        "effective_d": surface.effective_d,
        "active": surface.governor_active,
    }


def _baseline_titles(deps: AgentDeps) -> dict[str, float] | None:
    if deps.forecaster is None:
        return None
    return deps.forecaster.title_probs(n_sims=_BASELINE_SIMS, seed=0)


def _market_titles(deps: AgentDeps) -> dict[str, float] | None:
    from wolves.markets.series import load_series

    series = load_series(deps.settings.runs_root / "odds-archive")
    latest = next((p for p in reversed(series) if p.outright_bookmakers), None)
    return latest.outright_bookmakers if latest else None


def _previous_titles(deps: AgentDeps) -> dict[str, float] | None:
    from datetime import date

    from wolves.agent.scoring import latest_snapshot_by_kind

    if not deps.as_of or deps.disable_continuity:
        return None
    previous = latest_snapshot_by_kind(
        deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of), kind="agent"
    )
    if previous is None:
        return None
    return {t.team_id: t.champion_prob for t in previous.teams}


def spread_section(deps: AgentDeps, artifact_id: str) -> dict | None:
    """The spread rows for the cited mixture, cached per artifact id on the run."""
    from wolves.agent.tools.simulation.mixture_spread import spread_for_artifact

    cache = deps.submission.spread_by_artifact
    if artifact_id not in cache:
        cache[artifact_id] = spread_for_artifact(deps, artifact_id)
    return cache[artifact_id]


def factor_audit_section(deps: AgentDeps, artifact_id: str) -> dict | None:
    if deps.artifacts is None:
        return None
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return None
    audit = artifact.payload.get("factor_audit")
    return audit if isinstance(audit, dict) else None


def branch_audit_section(deps: AgentDeps, artifact_id: str) -> dict | None:
    if deps.artifacts is None:
        return None
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return None
    audit = artifact.payload.get("branch_audit")
    return audit if isinstance(audit, dict) else None


def world_metadata_section(deps: AgentDeps, artifact_id: str) -> dict | None:
    if deps.artifacts is None:
        return None
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return None
    metadata = artifact.payload.get("world_metadata")
    return metadata if isinstance(metadata, dict) else None


def market_gap_contract(deps: AgentDeps, args: ForecastSubmission) -> MarketGapContract:
    market_titles = _anchors(deps).market_titles or {}
    preview = published_title_preview(deps, args.artifact_id)
    titles = preview["titles"]
    submitted: list[dict[str, object]] = []
    for gap in args.market_gaps:
        computed_gap_pp = abs((gap.market_prob - gap.model_prob) * 100)
        submitted.append(
            {
                "team_id": gap.team_id,
                "model_prob": gap.model_prob,
                "market_prob": gap.market_prob,
                "gap_pp": gap.gap_pp,
                "computed_gap_pp": round(computed_gap_pp, 2),
                "coherent": abs(gap.gap_pp - computed_gap_pp) <= 0.2,
                "direction": "market_higher" if gap.market_prob >= gap.model_prob else "market_lower",
            }
        )
    anchor_gaps = [
        {
            "team_id": team,
            "published_prob": published,
            "market_prob": market_titles[team],
            "gap_pp": round((published - market_titles[team]) * 100, 2),
            "beyond_threshold": _beyond_market_threshold(published, market_titles[team], deps),
        }
        for team, published in titles.items()
        if team in market_titles
    ]
    anchor_gaps.sort(key=lambda row: abs(float(row["gap_pp"])), reverse=True)
    return {"submitted": submitted, "anchor_gaps": anchor_gaps[:12]}


def _beyond_market_threshold(published: float, market: float, deps: AgentDeps) -> bool:
    scale = min(1.0, market / deps.limits.escalation_reference_p) if deps.limits.escalation_reference_p > 0 else 1.0
    threshold = deps.limits.escalation_threshold_pp * max(scale, 0.05)
    return abs((published - market) * 100) > threshold


def branch_advisories(deps: AgentDeps, artifact_id: str) -> list[dict[str, str]]:
    if deps.artifacts is None:
        return []
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return []
    payload = artifact.payload
    advisories: list[dict[str, str]] = []
    branch_keys = _candidate_branch_keys(deps)
    branch_audit = payload.get("branch_audit")
    if branch_keys and not isinstance(branch_audit, dict):
        advisories.append(
            {
                "code": "candidate_branches_unaccounted",
                "message": (
                    "research proposed candidate branches but the mixture has no branch_audit; this is allowed, "
                    f"but forecast should explain priced, collapsed or rejected branches: {', '.join(branch_keys[:6])}"
                ),
            }
        )
    elif branch_keys:
        checked = _branch_audit_keys(branch_audit)
        missing = sorted(set(branch_keys) - checked)
        if missing:
            advisories.append(
                {
                    "code": "candidate_branches_missing_from_audit",
                    "message": (
                        "branch_audit is present but does not mention every research candidate branch; "
                        "forecast should explain the missing branches or have quant update the audit: "
                        f"{', '.join(missing[:6])}"
                    ),
                }
            )
    metadata = payload.get("world_metadata")
    weights = payload.get("weights") or {}
    generic = sorted(
        name
        for name in weights
        if name not in _BASE_WORLDS and (name in _GENERIC_WORLD_NAMES or name.endswith("_evidence"))
    )
    if generic and not isinstance(metadata, dict):
        advisories.append(
            {
                "code": "generic_world_metadata_missing",
                "message": (
                    "generic non-base world names are allowed but should usually carry world_metadata or be "
                    f"explained in the journal: {', '.join(generic)}"
                ),
            }
        )
    elif generic:
        incomplete = [
            name
            for name in generic
            if not isinstance(metadata.get(name), dict)
            or not str(metadata[name].get("label") or "").strip()
            or not str(metadata[name].get("summary") or "").strip()
        ]
        if incomplete:
            advisories.append(
                {
                    "code": "generic_world_metadata_incomplete",
                    "message": (
                        "world_metadata should give generic non-base worlds a plain label and summary: "
                        + ", ".join(incomplete)
                    ),
                }
            )
    if isinstance(metadata, dict):
        hidden = _live_branch_worlds_in_generic_camps(metadata, weights)
        if hidden:
            advisories.append(
                {
                    "code": "live_branch_hidden_in_generic_camp",
                    "message": (
                        "these non-base worlds carry live branch keys but sit in generic model/market camps; "
                        "check whether the camp label still names the real lens: " + ", ".join(hidden)
                    ),
                }
            )
    return advisories


def _live_branch_worlds_in_generic_camps(metadata: dict, weights: dict) -> list[str]:
    hidden: list[str] = []
    for name in weights:
        if name in _BASE_WORLDS:
            continue
        row = metadata.get(name)
        if not isinstance(row, dict):
            continue
        branch_keys = row.get("branch_keys")
        camp = str(row.get("camp") or "").strip().lower()
        if isinstance(branch_keys, list) and branch_keys and camp in {"model", "market"}:
            hidden.append(name)
    return sorted(hidden)


def _branch_audit_keys(audit: object) -> set[str]:
    if not isinstance(audit, dict):
        return set()
    checks = audit.get("checks")
    if not isinstance(checks, list):
        return set()
    return {str(check.get("key")) for check in checks if isinstance(check, dict) and check.get("key")}


def _candidate_branch_keys(deps: AgentDeps) -> list[str]:
    if deps.artifacts is None:
        return []
    keys: list[str] = []
    for record in deps.artifacts.all():
        if record.kind != "evidence":
            continue
        artifact = deps.artifacts.get(record.id)
        if artifact is None:
            continue
        branches = artifact.payload.get("candidate_branches")
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if isinstance(branch, dict) and branch.get("branch_id"):
                key = str(branch["branch_id"])
                if key not in keys:
                    keys.append(key)
    return keys


def _focus_vs_floor(spread: dict | None, focus_team: str) -> float | None:
    if spread is None:
        return None
    row = next((r for r in spread["teams"] if r["team"] == focus_team), None)
    return row["vs_floor"] if row else None


def validation_report(args: ForecastSubmission, deps: AgentDeps) -> ValidationReport:
    anchors = _anchors(deps)
    spread = spread_section(deps, args.artifact_id)
    preview = published_title_preview(deps, args.artifact_id)
    return validate_submission(
        args,
        artifacts=deps.artifacts,
        ledger=deps.ledger,
        limits=deps.limits,
        baseline_titles=anchors.baseline_titles,
        previous_titles=_previous_titles(deps),
        market_titles=anchors.market_titles,
        published_titles=preview["titles"],
        focus_vs_floor=_focus_vs_floor(spread, deps.settings.focus_team),
    )
