"""Select a complete forecast and normalise its historic result view."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from wolves.archive.contracts import ARCHIVE_TIMEZONE, ArchivedResult, FixtureMetadata
from wolves.snapshot import ResultSetEntry, Snapshot


class ArchiveSelectionError(ValueError):
    """The source cannot produce a coherent archive view."""


def archive_cutoff(day: str) -> datetime:
    """Return the New York end-of-day cutoff for an archive day."""
    try:
        selected_day = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ArchiveSelectionError(f"invalid archive day {day!r}") from exc
    return datetime.combine(selected_day, time.max, tzinfo=ZoneInfo(ARCHIVE_TIMEZONE)).astimezone(UTC)


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp into UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArchiveSelectionError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ArchiveSelectionError(f"timestamp needs an offset: {value!r}")
    return parsed.astimezone(UTC)


def select_snapshot(snapshots: list[Snapshot], *, cutoff: datetime) -> Snapshot:
    """Select the newest complete agent snapshot at or before a cutoff."""
    eligible = [snapshot for snapshot in snapshots if parse_timestamp(snapshot.run.created_at) <= cutoff]
    agent = [snapshot for snapshot in eligible if snapshot.run.kind == "agent"]
    candidates = agent or eligible
    if not candidates:
        raise ArchiveSelectionError(f"no complete snapshot exists at or before {cutoff.isoformat()}")
    return max(candidates, key=lambda snapshot: parse_timestamp(snapshot.run.created_at))


def normalise_results(
    snapshot: Snapshot,
    *,
    cutoff: datetime,
    fixture_metadata: dict[int, FixtureMetadata] | None = None,
) -> list[ArchivedResult]:
    """Return only results provably known by the selected archive cutoff."""
    fixtures = {
        fixture.match: (fixture.date, fixture.stage, fixture.home_id, fixture.away_id)
        for fixture in snapshot.matches
    }
    for slot in snapshot.slots:
        fixtures.setdefault(slot.match, (slot.date, slot.stage, None, None))

    results: list[ArchivedResult] = []
    for entry in snapshot.result_set.results:
        recorded_at = parse_timestamp(entry.fetched_at or snapshot.run.created_at)
        if recorded_at > cutoff:
            continue
        fixture = fixtures.get(entry.match)
        if fixture is None:
            metadata = (fixture_metadata or {}).get(entry.match)
            if metadata is not None:
                fixture = (metadata.date, metadata.stage, None, None)
        if fixture is None:
            raise ArchiveSelectionError(
                f"result match {entry.match} in {snapshot.run.run_id} has no fixture or slot for normalisation"
            )
        date, stage, home_id, away_id = fixture
        results.append(
            _normalise_result(
                entry,
                date=date,
                stage=stage,
                home_id=home_id,
                away_id=away_id,
                recorded_at=recorded_at,
            )
        )
    return sorted(results, key=lambda result: (result.date, result.match))


def _normalise_result(
    entry: ResultSetEntry,
    *,
    date: str,
    stage: str,
    home_id: str | None,
    away_id: str | None,
    recorded_at: datetime,
) -> ArchivedResult:
    return ArchivedResult(
        match=entry.match,
        date=date,
        stage=stage,
        home_id=entry.home_id or home_id,
        away_id=entry.away_id or away_id,
        home_goals=entry.home_goals,
        away_goals=entry.away_goals,
        winner=entry.winner,
        recorded_at=recorded_at.isoformat().replace("+00:00", "Z"),
    )
