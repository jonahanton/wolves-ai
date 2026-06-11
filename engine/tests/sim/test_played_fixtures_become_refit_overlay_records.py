from __future__ import annotations

from datetime import datetime

from wolves.clients.api_football import MatchFixture
from wolves.config import Settings
from wolves.s3.artifacts import ArtifactStore
from wolves.sim.results_store import ResultsStore, played_match_records


def _fixture(fixture_id: int, home: str, away: str, *, status: str = "finished", goals=(2, 0)) -> MatchFixture:
    return MatchFixture(
        fixture_id=fixture_id,
        kickoff=datetime.fromisoformat("2026-06-11T13:00:00-06:00"),
        status=status,
        home=home,
        away=away,
        home_goals=goals[0] if status == "finished" else None,
        away_goals=goals[1] if status == "finished" else None,
    )


def test_finished_fixtures_convert_with_canonical_keys_and_host_neutrality(tmp_path):
    settings = Settings(runs_root=tmp_path, storage_mode="local")
    ResultsStore(ArtifactStore(settings)).record(
        {},
        fixtures=[
            _fixture(1, "Mexico", "South Africa"),
            _fixture(2, "England", "Croatia"),
            _fixture(3, "Spain", "Japan", status="live"),
        ],
    )

    records = {r.home_team: r for r in played_match_records(settings)}

    assert set(records) == {"mexico", "england"}
    assert records["mexico"].neutral is False
    assert records["england"].neutral is True
    assert records["england"].away_team == "croatia"
    assert records["england"].tournament == "FIFA World Cup"
