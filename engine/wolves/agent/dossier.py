"""The morning dossier: the deterministic preamble the master wakes to.

Assembled for free before any LLM call; every block degrades to absence so
a missing archive or empty ledger never blocks the run."""

from __future__ import annotations

import logging
from datetime import date

from wolves.agent.calibration import CalibrationLedger, summarise_scores
from wolves.agent.deps import AgentDeps
from wolves.agent.knockout_slots import format_slot_rationale_brief, open_knockout_rationale_slots
from wolves.insights.market import market_movement
from wolves.insights.market_gaps import market_gaps

logger = logging.getLogger(__name__)

_TOP_TEAMS = 10
_DOSSIER_SIMS = 50_000


def build_dossier(deps: AgentDeps) -> str:
    """Baseline digest, gap table, noise-floored movement, fresh ledger and
    the calibration readback, as one prompt block. The baseline simulation is
    computed once and shared so the preamble stays seconds, not tens."""
    titles: dict[str, float] | None = None
    if deps.forecaster is not None:
        try:
            titles = deps.forecaster.title_probs(n_sims=_DOSSIER_SIMS, seed=0)
        except Exception as exc:
            logger.warning("dossier baseline skipped: %s", exc)
    sections: list[str] = []
    for build in (
        _what_changed,
        _tournament,
        _knockout_rationales,
        _baseline,
        _gaps,
        _published,
        _movement,
        _matchday,
        _scenarios,
        _ledger,
        _calibration,
    ):
        try:
            section = build(deps, titles)
        except Exception as exc:
            logger.warning("dossier section %s skipped: %s", build.__name__, exc)
            continue
        if section:
            sections.append(section)
    return "\n\n".join(sections)


def previous_agent_anchor(deps: AgentDeps, *, top_n: int = _TOP_TEAMS) -> str:
    from datetime import UTC, datetime

    from wolves.agent.scoring import latest_snapshot_by_kind
    from wolves.insights.what_changed import load_latest_snapshot

    if not deps.as_of:
        return ""
    snapshot_dir = deps.settings.runs_root / "snapshots"
    latest = load_latest_snapshot(snapshot_dir, before=date.fromisoformat(deps.as_of))
    previous = latest_snapshot_by_kind(snapshot_dir, before=date.fromisoformat(deps.as_of), kind="agent") or latest
    if previous is None:
        return ""
    top = sorted(previous.teams, key=lambda t: t.champion_prob, reverse=True)[:top_n]
    rows = ", ".join(f"{t.team_id} {t.champion_prob * 100:.1f}" for t in top)
    when = previous.run.created_at
    try:
        age_h = (datetime.now(UTC) - datetime.fromisoformat(when)).total_seconds() / 3600
        when = f"{when}, {age_h:.0f}h ago"
    except ValueError:
        pass
    worlds = ""
    if previous.agent is not None and previous.agent.worlds:
        worlds = " Its worlds: " + ", ".join(f"{w.name} {w.weight:.2f}" for w in previous.agent.worlds[:8]) + "."
    live_note = ""
    if latest is not None and latest.run.run_id != previous.run.run_id:
        live_note = f" Latest live snapshot is {latest.run.run_id}; use it for settled state, not continuity."
    return (
        f"Previous agent forecast ({previous.run.run_id}, {previous.run.kind}, created {when}): {rows}.{worlds}"
        f"{live_note} "
        "This is not a first run. It is the anchor your run moves from; unexplained drift against it is rejected "
        "at submission. Nodes can open its full narrative, evidence and artifact index with previous_forecast."
    )


def _what_changed(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    from datetime import date as _date

    from wolves.agent.scoring import latest_snapshot_by_kind
    from wolves.insights.what_changed import diff_inputs, load_latest_snapshot, what_changed

    if not deps.as_of:
        return ""
    previous = latest_snapshot_by_kind(
        deps.settings.runs_root / "snapshots", before=_date.fromisoformat(deps.as_of), kind="agent"
    )
    previous = previous or load_latest_snapshot(
        deps.settings.runs_root / "snapshots", before=_date.fromisoformat(deps.as_of)
    )
    played, market_moves, fixtures = diff_inputs(
        previous=previous,
        forecaster=deps.forecaster,
        archive_dir=deps.settings.runs_root / "odds-archive",
        as_of=deps.as_of,
        move_floor_pp=deps.settings.market_movement_noise_floor_pp,
    )
    return what_changed(
        previous=previous,
        current_titles=titles,
        ledger=deps.ledger,
        source_memory=deps.source_memory,
        run_id=deps.runtime.run_id,
        as_of=deps.as_of,
        played_results=played,
        market_moves_pp=market_moves,
        upcoming_fixtures=fixtures,
    ).digest()


def _tournament(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    from wolves.sim.results_store import persisted_results

    fc = deps.forecaster
    if fc is None or not deps.as_of:
        return ""
    played = persisted_results(deps.settings)
    today = date.fromisoformat(deps.as_of)
    fixtures = [
        f"m{m.match} {m.home} v {m.away} ({m.date[:10]})"
        for m in sorted(fc.fmt.group_matches + fc.fmt.knockout, key=lambda m: m.date)
        if m.match not in played and 0 <= (date.fromisoformat(m.date[:10]) - today).days <= 1
    ]
    parts = []
    if played:
        group_results = [m for m in fc.fmt.group_matches if m.match in played]
        points: dict[str, dict[str, int]] = {}
        for m in group_results:
            r = played[m.match]
            home_pts = 3 if r.home_goals > r.away_goals else (1 if r.home_goals == r.away_goals else 0)
            for team, pts in ((m.home, home_pts), (m.away, 3 - home_pts if home_pts != 1 else 1)):
                points.setdefault(m.group, {})[team] = points.get(m.group, {}).get(team, 0) + pts
        standings = "; ".join(
            f"{group}: " + ", ".join(f"{t} {p}" for t, p in sorted(table.items(), key=lambda kv: -kv[1]))
            for group, table in sorted(points.items())
        )
        parts.append(f"Results so far: {len(played)} played. Group points: {standings}.")
    if fixtures:
        parts.append(f"Fixtures today and tomorrow: {', '.join(fixtures[:16])}.")
    return " ".join(parts)


def _knockout_rationales(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    fc = deps.forecaster
    if fc is None:
        return ""
    from wolves.sim.results_store import persisted_results

    slots = open_knockout_rationale_slots(fc.fmt, fc.played_results(extra_results=persisted_results(deps.settings)))
    return format_slot_rationale_brief(slots)


def _matchday(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    """Group-stage leverage for an imminent focus-team fixture, plus evidence
    expiring before kickoff; title pp alone hides group-stage action."""
    from wolves.forecast import ScorelinePerturbation

    fc = deps.forecaster
    if fc is None or not deps.as_of:
        return ""
    focus = deps.settings.focus_team
    today = date.fromisoformat(deps.as_of)
    fixture = next(
        (
            m
            for m in sorted(fc.fmt.group_matches, key=lambda m: m.date)
            if focus in (m.home, m.away) and 0 <= (date.fromisoformat(m.date[:10]) - today).days <= 1
        ),
        None,
    )
    if fixture is None:
        return ""
    home = fixture.home == focus
    outcomes = {"win": (2, 0) if home else (0, 2), "draw": (1, 1), "loss": (0, 1) if home else (1, 0)}
    base = (titles or fc.title_probs(n_sims=_DOSSIER_SIMS, seed=0))[focus]
    deltas = []
    for label, (hg, ag) in outcomes.items():
        pinned = ScorelinePerturbation(match=fixture.match, home_goals=hg, away_goals=ag, reason="leverage")
        moved = fc.title_probs(n_sims=_DOSSIER_SIMS, seed=0, perturbations=(pinned,))[focus]
        deltas.append(f"{label} {(moved - base) * 100:+.2f}pp")
    expiring = [
        e.id
        for e in deps.ledger.all()
        if e.expiry is not None and date.fromisoformat(e.expiry) <= date.fromisoformat(fixture.date[:10])
    ]
    expiry_note = f" Evidence expiring by kickoff: {', '.join(expiring)}." if expiring else ""
    return (
        f"Matchday: {focus} play {fixture.away if home else fixture.home} ({fixture.date[:10]}, match "
        f"{fixture.match}). Title leverage: {', '.join(deltas)}; read the move through group-win and "
        f"qualification lenses, not title pp.{expiry_note}"
    )


def _scenarios(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    if deps.scenarios is None:
        return ""
    open_states = [s for s in deps.scenarios.open_scenarios() if s.weight > 0]
    if not open_states:
        return ""
    rows = "; ".join(
        f"{s.scenario_id} {s.name} (w={s.weight:.2f}, {s.status}; latest: {s.history[-1].reason})"
        for s in open_states
    )
    return (
        "Open internal scenarios for forecast or quant to resolve with scenario_update. The scn-* keys "
        f"are private registry ids, not web search terms; search only the named football story: {rows}."
    )


def _baseline(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    if titles is None:
        return ""
    top = sorted(titles.items(), key=lambda kv: kv[1], reverse=True)[:_TOP_TEAMS]
    rows = ", ".join(f"{team} {p * 100:.1f}" for team, p in top)
    return f"Baseline title probabilities (pp, {_DOSSIER_SIMS // 1000}k sims): {rows}."


def _price_freshness(oldest: str | None, newest: str | None) -> str:
    if oldest is None or newest is None:
        return ""
    if oldest == newest:
        return f" Prices updated at {oldest}."
    return f" Prices updated between {oldest} and {newest}."


def _gaps(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    if deps.forecaster is None:
        return ""
    table = market_gaps(deps.forecaster, deps.settings.runs_root / "odds-archive", n_sims=_DOSSIER_SIMS, seed=0)
    priced = [c for c in table.gaps if c.market_p_title is not None][:8]
    rows = "; ".join(
        f"{c.team}: model {c.model_p_title * 100:.1f} vs market {c.market_p_title * 100:.1f} ({c.gap_pp:+.1f}pp"
        + (f", blend {c.blend_p_title * 100:.1f}" if c.blend_p_title is not None else "")
        + ")"
        for c in priced
    )
    freshness = _price_freshness(table.prices_updated_oldest, table.prices_updated_newest)
    if not rows:
        return ""
    return (
        f"Model vs market, largest gaps: {rows}. The submitted mixture publishes as-is, no market leg is "
        f"added, so every large gap must be reconciled inside the mixture: priced as a weighted world or "
        f"disputed with a computation. The blend column is reference only (weight {table.model_weight:.2f})."
        f"{freshness}"
    )


def _published(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    return previous_agent_anchor(deps, top_n=_TOP_TEAMS)


def _movement(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    if deps.forecaster is None:
        return ""
    floor = deps.settings.market_movement_noise_floor_pp
    movement = market_movement(deps.settings.runs_root / "odds-archive", deps.forecaster.fmt, history_points=4)
    movers = [
        f"{m.team} {m.delta_pp_vs_previous:+.1f}pp"
        for m in movement.outright_bookmakers
        if m.delta_pp_vs_previous is not None and abs(m.delta_pp_vs_previous) >= floor
    ]
    freshness = _price_freshness(movement.prices_updated_oldest, movement.prices_updated_newest)
    if not movers:
        return f"Market movement: nothing beyond the {floor}pp noise floor.{freshness}"
    return f"Market movers beyond the {floor}pp noise floor: {', '.join(movers[:8])}.{freshness}"


def _ledger(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    fresh = deps.ledger.query(fresh_on=date.fromisoformat(deps.as_of)) if deps.as_of else deps.ledger.all()
    if not fresh:
        return ""
    rows = "; ".join(f"{e.id} [{e.status}] {e.claim[:60]}" for e in fresh[-8:])
    return f"Unexpired ledger evidence: {rows}."


def _calibration(deps: AgentDeps, titles: dict[str, float] | None) -> str:
    scores = CalibrationLedger(deps.settings.calibration_path).scores()
    return summarise_scores(scores, window=deps.settings.governor_window)
