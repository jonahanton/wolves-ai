"""Score yesterday's forecasts before the governor reads the ledger, so
today's delta caps already reflect yesterday's P&L."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from pydantic import ValidationError

from wolves.agent.calibration import CalibrationLedger, MatchForecast, MatchScore, score_match, summarise_scores
from wolves.agent.memory import RunMemory
from wolves.config import Settings
from wolves.sim.format import PlayedResult, load_results
from wolves.snapshot import MatchProbs, Snapshot

logger = logging.getLogger(__name__)


def load_previous_snapshots(snapshot_dir: Path, *, before: date) -> tuple[Snapshot | None, Snapshot | None]:
    """Return (latest snapshot, latest sim-only snapshot) created before the date."""
    latest: Snapshot | None = None
    baseline: Snapshot | None = None
    if not snapshot_dir.exists():
        return None, None
    for path in snapshot_dir.rglob("*.json"):
        if path.name == "latest.json":
            continue
        try:
            snapshot = Snapshot.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            logger.warning("skipping unreadable snapshot %s", path)
            continue
        if datetime.fromisoformat(snapshot.run.created_at).date() >= before:
            continue
        if latest is None or snapshot.run.created_at > latest.run.created_at:
            latest = snapshot
        if snapshot.run.kind == "sim_only" and (baseline is None or snapshot.run.created_at > baseline.run.created_at):
            baseline = snapshot
    return latest, baseline


def _outcome(result: PlayedResult) -> str:
    if result.home_goals > result.away_goals:
        return "home"
    if result.home_goals < result.away_goals:
        return "away"
    return "draw"


def _probs(entry: MatchProbs) -> dict[str, float]:
    assert entry.p_draw is not None
    return {"home": entry.p_home, "draw": entry.p_draw, "away": entry.p_away}


def score_resolved_matches(
    *,
    previous: Snapshot,
    baseline: Snapshot | None,
    results: dict[int, PlayedResult],
    ledger: CalibrationLedger,
) -> list[MatchScore]:
    """Score the previous snapshot's group-match forecasts that now have results."""
    already = {score.match_id for score in ledger.scores()}
    baseline_entries = {entry.match: entry for entry in baseline.matches} if baseline else {}
    adjusted_teams: set[str] = set()
    if previous.agent is not None:
        for world in previous.agent.worlds:
            for perturbation in world.perturbations:
                team = perturbation.get("team")
                if isinstance(team, str):
                    adjusted_teams.add(team)

    scores: list[MatchScore] = []
    for entry in previous.matches:
        result = results.get(entry.match)
        if entry.p_draw is None or result is None or str(entry.match) in already:
            continue
        frozen = baseline_entries.get(entry.match)
        forecast = MatchForecast(
            match_id=str(entry.match),
            date=entry.date,
            home=entry.home_id,
            away=entry.away_id,
            model_probs=_probs(entry),
            frozen_sim_probs=_probs(frozen) if frozen else None,
            adjusted=bool({entry.home_id, entry.away_id} & adjusted_teams),
        )
        score = score_match(forecast, _outcome(result))
        ledger.append(score)
        scores.append(score)
    return scores


def score_yesterday(settings: Settings, *, as_of: str, run_id: str) -> str:
    """Score forecasts that resolved since the previous run and record the
    scorecard as a lesson; return the summary (empty when nothing scored)."""
    previous, baseline = load_previous_snapshots(settings.runs_root / "snapshots", before=date.fromisoformat(as_of))
    if previous is None:
        return ""
    ledger = CalibrationLedger(settings.calibration_path)
    scores = score_resolved_matches(
        previous=previous,
        baseline=baseline,
        results=load_results(settings.data_dir),
        ledger=ledger,
    )
    if not scores:
        return ""
    summary = summarise_scores(ledger.scores(), window=settings.governor_window)
    memory = RunMemory(runs_root=settings.runs_root, run_id=run_id, lessons_path=settings.lessons_path)
    memory.append_lessons(summary)
    logger.info("calibration: scored %d match(es) from %s", len(scores), previous.run.run_id)
    return summary
