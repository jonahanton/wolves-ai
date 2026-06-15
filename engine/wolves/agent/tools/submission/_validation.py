"""Shared validator invocation for the submission tools: resolves the anchor
distributions (frozen baseline, previous published forecast, de-vigged market)
and runs the deterministic validator over a submission. The baseline and
market anchors resolve once per run, cached on the shared SubmissionState."""

from __future__ import annotations

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps, ValidatorAnchors
from wolves.agent.validator import ValidationReport, validate_submission

_BASELINE_SIMS = 50_000


def _anchors(deps: AgentDeps) -> ValidatorAnchors:
    if deps.submission.anchors is None:
        deps.submission.anchors = ValidatorAnchors(
            baseline_titles=_baseline_titles(deps), market_titles=_market_titles(deps)
        )
    return deps.submission.anchors


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

    from wolves.insights.what_changed import load_latest_snapshot

    if not deps.as_of:
        return None
    previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of))
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


def _focus_vs_floor(spread: dict | None, focus_team: str) -> float | None:
    if spread is None:
        return None
    row = next((r for r in spread["teams"] if r["team"] == focus_team), None)
    return row["vs_floor"] if row else None


def validation_report(args: ForecastSubmission, deps: AgentDeps) -> ValidationReport:
    anchors = _anchors(deps)
    spread = spread_section(deps, args.artifact_id)
    return validate_submission(
        args,
        artifacts=deps.artifacts,
        ledger=deps.ledger,
        limits=deps.limits,
        baseline_titles=anchors.baseline_titles,
        previous_titles=_previous_titles(deps),
        market_titles=anchors.market_titles,
        focus_vs_floor=_focus_vs_floor(spread, deps.settings.focus_team),
    )
