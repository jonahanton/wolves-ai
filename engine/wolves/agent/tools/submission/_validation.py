"""Shared validator invocation for the submission tools: resolves the anchor
distributions (frozen baseline, previous published forecast, de-vigged market)
and runs the deterministic validator over a submission."""

from __future__ import annotations

from wolves.agent.contracts import ForecastSubmission
from wolves.agent.deps import AgentDeps
from wolves.agent.validator import ValidationReport, validate_submission

_BASELINE_SIMS = 50_000


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


def validation_report(args: ForecastSubmission, deps: AgentDeps) -> ValidationReport:
    return validate_submission(
        args,
        artifacts=deps.artifacts,
        ledger=deps.ledger,
        limits=deps.limits,
        baseline_titles=_baseline_titles(deps),
        previous_titles=_previous_titles(deps),
        market_titles=_market_titles(deps),
        focus_team=deps.settings.focus_team,
    )
