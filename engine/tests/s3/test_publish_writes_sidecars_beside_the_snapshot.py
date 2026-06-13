from __future__ import annotations

import json
from datetime import date

import pytest

from wolves.config import Settings
from wolves.run import generate_snapshot
from wolves.s3.publish import SnapshotPublisher
from wolves.sidecars import MatchWdl, MatchWdlDraws, UnknownSidecarError

AS_OF = date(2026, 6, 17)


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory):
    settings = Settings(runs_root=tmp_path_factory.mktemp("fresh-runs"), storage_mode="local")
    snapshot, _ = generate_snapshot(settings, n_sims=200, seed=7, run_id="run-20260617")
    return snapshot


def _payload() -> MatchWdlDraws:
    return MatchWdlDraws(matches={2: MatchWdl(p_home=[0.5], p_draw=[0.3], p_away=[0.2])})


def test_sidecars_land_on_dataset_suffixed_keys(snapshot, tmp_path):
    settings = Settings(storage_mode="local", runs_root=tmp_path, dynamo_endpoint="")
    publisher = SnapshotPublisher(settings)

    publisher.publish(snapshot, as_of=AS_OF, started=0.0, sidecars={"match-wdl-draws": _payload()})

    blob = tmp_path / "snapshots" / "2026" / "06" / "17" / "run-20260617.match-wdl-draws.json"
    assert json.loads(blob.read_text())["matches"]["2"]["p_home"] == [0.5]
    assert (tmp_path / "snapshots" / "2026" / "06" / "17" / "run-20260617.json").exists()


def test_unknown_sidecar_name_is_rejected(snapshot, tmp_path):
    settings = Settings(storage_mode="local", runs_root=tmp_path, dynamo_endpoint="")
    with pytest.raises(UnknownSidecarError):
        SnapshotPublisher(settings).publish(snapshot, as_of=AS_OF, started=0.0, sidecars={"nope": _payload()})
