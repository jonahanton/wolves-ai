"""The morning dossier: the deterministic preamble the master wakes to.

Assembled for free before any LLM call; every block degrades to absence so
a missing archive or empty ledger never blocks the run."""

from __future__ import annotations

import logging
from datetime import date

from wolves.agent.calibration import CalibrationLedger, summarise_scores
from wolves.agent.deps import AgentDeps
from wolves.insights.market import market_movement
from wolves.insights.model_vs_market import model_vs_market

logger = logging.getLogger(__name__)

_TOP_TEAMS = 10
_DOSSIER_SIMS = 50_000


def build_dossier(deps: AgentDeps) -> str:
    """Baseline digest, gap table, noise-floored movement, fresh ledger and
    the calibration readback, as one prompt block."""
    sections: list[str] = []
    for build in (_what_changed, _baseline, _gaps, _movement, _matchday, _scenarios, _ledger, _calibration):
        try:
            section = build(deps)
        except Exception as exc:
            logger.warning("dossier section %s skipped: %s", build.__name__, exc)
            continue
        if section:
            sections.append(section)
    return "\n\n".join(sections)


def _what_changed(deps: AgentDeps) -> str:
    from datetime import date as _date

    from wolves.insights.what_changed import load_latest_snapshot, what_changed

    if not deps.as_of:
        return ""
    previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=_date.fromisoformat(deps.as_of))
    titles = deps.forecaster.title_probs(n_sims=_DOSSIER_SIMS, seed=0) if deps.forecaster is not None else None
    return what_changed(
        previous=previous,
        current_titles=titles,
        ledger=deps.ledger,
        source_memory=deps.source_memory,
        run_id=deps.runtime.run_id,
        as_of=deps.as_of,
    ).digest()


def _matchday(deps: AgentDeps) -> str:
    """Group-stage leverage for an imminent England fixture, plus evidence
    expiring before kickoff; title pp alone hides group-stage action."""
    from wolves.forecast import ScorelinePerturbation

    fc = deps.forecaster
    if fc is None or not deps.as_of:
        return ""
    today = date.fromisoformat(deps.as_of)
    fixture = next(
        (
            m
            for m in sorted(fc.fmt.group_matches, key=lambda m: m.date)
            if "england" in (m.home, m.away) and 0 <= (date.fromisoformat(m.date[:10]) - today).days <= 1
        ),
        None,
    )
    if fixture is None:
        return ""
    home = fixture.home == "england"
    outcomes = {"win": (2, 0) if home else (0, 2), "draw": (1, 1), "loss": (0, 1) if home else (1, 0)}
    base = fc.title_probs(n_sims=_DOSSIER_SIMS, seed=0)["england"]
    deltas = []
    for label, (hg, ag) in outcomes.items():
        pinned = ScorelinePerturbation(match=fixture.match, home_goals=hg, away_goals=ag, reason="leverage")
        moved = fc.title_probs(n_sims=_DOSSIER_SIMS, seed=0, perturbations=(pinned,))["england"]
        deltas.append(f"{label} {(moved - base) * 100:+.2f}pp")
    expiring = [
        e.id
        for e in deps.ledger.all()
        if e.expiry is not None and date.fromisoformat(e.expiry) <= date.fromisoformat(fixture.date[:10])
    ]
    expiry_note = f" Evidence expiring by kickoff: {', '.join(expiring)}." if expiring else ""
    return (
        f"Matchday: England play {fixture.away if home else fixture.home} ({fixture.date[:10]}, match "
        f"{fixture.match}). Title leverage: {', '.join(deltas)}; read the move through group-win and "
        f"qualification lenses, not title pp.{expiry_note}"
    )


def _scenarios(deps: AgentDeps) -> str:
    if deps.scenarios is None:
        return ""
    open_states = deps.scenarios.open_scenarios()
    if not open_states:
        return ""
    rows = "; ".join(f"{s.scenario_id} {s.name} (w={s.weight:.2f}, {s.status})" for s in open_states)
    return (
        f"Open scenarios you must resolve today (collapse, reweight, carry or expire each "
        f"with scenario_update): {rows}."
    )


def _baseline(deps: AgentDeps) -> str:
    if deps.forecaster is None:
        return ""
    titles = deps.forecaster.title_probs(n_sims=_DOSSIER_SIMS, seed=0)
    top = sorted(titles.items(), key=lambda kv: kv[1], reverse=True)[:_TOP_TEAMS]
    rows = ", ".join(f"{team} {p * 100:.1f}" for team, p in top)
    return f"Baseline title probabilities (pp, {_DOSSIER_SIMS // 1000}k sims): {rows}."


def _gaps(deps: AgentDeps) -> str:
    if deps.forecaster is None:
        return ""
    table = model_vs_market(deps.forecaster, deps.settings.runs_root / "odds-archive", n_sims=_DOSSIER_SIMS, seed=0)
    priced = [c for c in table.comparisons if c.market_p_title is not None][:8]
    rows = "; ".join(
        f"{c.team}: model {c.model_p_title * 100:.1f} vs market {c.market_p_title * 100:.1f} ({c.gap_pp:+.1f}pp)"
        for c in priced
    )
    return f"Model vs market, largest gaps: {rows}." if rows else ""


def _movement(deps: AgentDeps) -> str:
    if deps.forecaster is None:
        return ""
    floor = deps.settings.market_movement_noise_floor_pp
    movement = market_movement(deps.settings.runs_root / "odds-archive", deps.forecaster.fmt, history_points=4)
    movers = [
        f"{m.team} {m.delta_pp_vs_previous:+.1f}pp"
        for m in movement.outright_bookmakers
        if m.delta_pp_vs_previous is not None and abs(m.delta_pp_vs_previous) >= floor
    ]
    if not movers:
        return f"Market movement: nothing beyond the {floor}pp noise floor."
    return f"Market movers beyond the {floor}pp noise floor: {', '.join(movers[:8])}."


def _ledger(deps: AgentDeps) -> str:
    fresh = deps.ledger.query(fresh_on=date.fromisoformat(deps.as_of)) if deps.as_of else deps.ledger.all()
    if not fresh:
        return ""
    rows = "; ".join(f"{e.id} [{e.status}] {e.claim[:60]}" for e in fresh[-8:])
    return f"Unexpired ledger evidence: {rows}."


def _calibration(deps: AgentDeps) -> str:
    scores = CalibrationLedger(deps.settings.calibration_path).scores()
    return summarise_scores(scores, window=deps.settings.governor_window)
