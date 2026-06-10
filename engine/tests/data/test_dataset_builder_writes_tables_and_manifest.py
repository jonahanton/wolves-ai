from __future__ import annotations

import json
from datetime import date

import duckdb
import pandas as pd

from wolves.data.build import write_dataset
from wolves.data.contracts import MatchRecord
from wolves.data.store import dataset_filename, dataset_id_from_hashes

HASHES = {"martj42_results": "abc"}
DATASET_ID = dataset_id_from_hashes(HASHES)


def _matches_frame() -> pd.DataFrame:
    record = MatchRecord(
        date=date(2022, 12, 18),
        home_team="argentina",
        away_team="france",
        home_goals=3,
        away_goals=3,
        tournament="FIFA World Cup",
        importance=4.0,
        neutral=True,
    )
    return pd.DataFrame([record.model_dump()])


def test_dataset_and_parquet_and_manifest_agree(tmp_path) -> None:
    manifest = write_dataset(tmp_path, tables={"matches": _matches_frame()}, hashes=HASHES)

    assert manifest.dataset_id == DATASET_ID
    connection = duckdb.connect(str(tmp_path / dataset_filename(DATASET_ID)))
    assert connection.execute("select home_team, away_goals from matches").fetchall() == [("argentina", 3)]
    parquet = connection.execute(f"select count(*) from '{tmp_path / 'parquet' / 'matches.parquet'}'").fetchone()
    assert parquet == (1,)
    connection.close()

    on_disk = json.loads((tmp_path / f"{dataset_filename(DATASET_ID)}.manifest.json").read_text(encoding="utf-8"))
    assert on_disk["tables"] == {"matches": 1} == manifest.tables
    assert on_disk["source_hashes"] == HASHES


def test_same_sources_rebuild_to_the_same_id_and_any_change_mints_a_new_one() -> None:
    assert dataset_id_from_hashes(HASHES) == DATASET_ID
    assert dataset_id_from_hashes({"martj42_results": "abd"}) != DATASET_ID
