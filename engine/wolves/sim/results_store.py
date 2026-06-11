"""Persisted played results: polled once by the live pass, read by every simulation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from wolves.clients.api_football import MatchFixture
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.client import S3UnavailableError
from wolves.s3.layout import RESULTS
from wolves.sim.format import PlayedResult

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wolves.config import Settings
    from wolves.data.contracts import MatchRecord

logger = logging.getLogger(__name__)


class StoredResults(BaseModel):
    fetched_at: str = ""
    results: dict[int, PlayedResult] = Field(default_factory=dict)
    fixtures: list[MatchFixture] = Field(default_factory=list)


class ResultsStore:
    """Merge-on-write store for the results blob; a partial poll never erases a known result."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def load(self) -> StoredResults:
        # Simulations must keep running when the bucket is unreachable, so an
        # outage degrades to the local mirror instead of killing the run.
        try:
            body = self._artifacts.get(RESULTS)
        except S3UnavailableError:
            if self._artifacts.mode == "s3":
                raise
            path = self._artifacts.local_path(RESULTS.key())
            body = path.read_text(encoding="utf-8") if path.exists() else None
            logger.warning("results blob unavailable in s3; using the local mirror")
        if body is None:
            return StoredResults()
        return StoredResults.model_validate_json(body)

    def record(
        self,
        results: dict[int, PlayedResult],
        *,
        fixtures: Sequence[MatchFixture] = (),
        fetched_at: str | None = None,
    ) -> StoredResults:
        """Merge newly polled results and finished fixtures into the blob; no-op writes are skipped."""
        known = self.load()
        merged_results = known.results | results
        by_id = {f.fixture_id: f for f in known.fixtures} | {f.fixture_id: f for f in fixtures}
        merged_fixtures = sorted(by_id.values(), key=lambda f: f.fixture_id)
        if merged_results == known.results and merged_fixtures == known.fixtures:
            return known
        merged = StoredResults(
            fetched_at=fetched_at or datetime.now(UTC).isoformat(timespec="seconds"),
            results=merged_results,
            fixtures=merged_fixtures,
        )
        self._artifacts.put(RESULTS, merged.model_dump_json())
        return merged


def persisted_results(settings: Settings) -> dict[int, PlayedResult]:
    """Hydrate and read the persisted results, keyed by match number."""
    return ResultsStore(ArtifactStore(settings)).load().results


_HOSTS = frozenset({"usa", "mexico", "canada"})
_WC_IMPORTANCE = 4.0


def played_match_records(settings: Settings) -> list[MatchRecord]:
    """Build refit overlay records from persisted tournament fixtures."""
    from wolves.data.contracts import MatchRecord
    from wolves.data.teams import registry_team_key
    from wolves.sim.format import load_format
    from wolves.sim.overlay import resolve_fixture

    fmt = load_format(settings.data_dir)
    by_match: dict[int, MatchRecord] = {}
    for fixture in stored_fixtures(settings):
        if fixture.status != "finished" or fixture.home_goals is None or fixture.away_goals is None:
            continue
        resolved = resolve_fixture(fmt, fixture)
        if resolved is None:
            continue
        if resolved.home_goals is None or resolved.away_goals is None:
            continue
        home = registry_team_key(resolved.home_id)
        by_match[resolved.match] = MatchRecord(
            date=fixture.kickoff.date(),
            home_team=home,
            away_team=registry_team_key(resolved.away_id),
            home_goals=resolved.home_goals,
            away_goals=resolved.away_goals,
            tournament="FIFA World Cup",
            importance=_WC_IMPORTANCE,
            neutral=resolved.home_id not in _HOSTS,
        )
    return [by_match[match] for match in sorted(by_match)]


def stored_fixtures(settings: Settings) -> list[MatchFixture]:
    """Hydrate and read the finished fixtures behind the persisted results."""
    return ResultsStore(ArtifactStore(settings)).load().fixtures
