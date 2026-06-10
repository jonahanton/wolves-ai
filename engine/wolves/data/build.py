"""Build the research dataset: one DuckDB file plus parquet mirrors."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import pandas as pd
from pydantic import BaseModel

from wolves import ENGINE_VERSION
from wolves.config import Settings
from wolves.data.contracts import DatasetManifest, MatchOddsRecord, MatchRecord, ShootoutRecord, TeamRecord
from wolves.data.sources import elo_history, football_data, market_closes, martj42
from wolves.data.sources.elo_history import EloHistoryRecord
from wolves.data.sources.market_closes import ClosingOddsRecord, OutrightCloseRecord
from wolves.data.sources.registry import build_team_dimension
from wolves.data.store import DatasetStore, dataset_filename, dataset_id_from_hashes
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.layout import ODDS_CLOSE

logger = logging.getLogger(__name__)


class RatingsSnapshotMissingError(Exception):
    def __init__(self, ratings_dir: Path) -> None:
        self.ratings_dir = ratings_dir
        super().__init__(f"no elo-*.tsv snapshot under {ratings_dir}")


def latest_elo_tsv(ratings_dir: Path) -> Path:
    candidates = sorted(p for p in ratings_dir.glob("elo-*.tsv") if p.name != "elo-team-codes.tsv")
    if not candidates:
        raise RatingsSnapshotMissingError(ratings_dir)
    return candidates[-1]


def _frame[T: BaseModel](records: list[T], model: type[T]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=list(model.model_fields))
    return pd.DataFrame([record.model_dump() for record in records])


def _sha256(text_or_bytes: str | bytes) -> str:
    data = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
    return hashlib.sha256(data).hexdigest()


def _dir_sha256(directory: Path) -> str:
    if not directory.exists():
        return "absent"
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*/*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_dataset(
    out_dir: Path, *, tables: dict[str, pd.DataFrame], hashes: dict[str, str], dataset_id: str | None = None
) -> DatasetManifest:
    dataset_id = dataset_id or dataset_id_from_hashes(hashes)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / dataset_filename(dataset_id)
    db_path.unlink(missing_ok=True)
    parquet_dir = out_dir / "parquet"
    parquet_dir.mkdir(exist_ok=True)

    connection = duckdb.connect(str(db_path))
    try:
        for name, frame in tables.items():
            connection.register("source_frame", frame)
            connection.execute(f"CREATE TABLE {name} AS SELECT * FROM source_frame")
            connection.unregister("source_frame")
            connection.execute(f"COPY {name} TO '{parquet_dir / f'{name}.parquet'}' (FORMAT PARQUET)")
    finally:
        connection.close()

    manifest = DatasetManifest(
        dataset_id=dataset_id,
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        engine_version=ENGINE_VERSION,
        tables={name: len(frame) for name, frame in tables.items()},
        source_hashes=hashes,
    )
    (out_dir / f"{dataset_filename(dataset_id)}.manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return manifest


async def build_dataset(settings: Settings, *, out_dir: Path) -> DatasetManifest:
    async with httpx.AsyncClient(timeout=60.0) as client:
        results_text = await martj42.fetch(martj42.RESULTS_URL, client=client)
        shootouts_text = await martj42.fetch(martj42.SHOOTOUTS_URL, client=client)
        workbook = await football_data.fetch_workbook(client=client)

    matches = martj42.parse_results(results_text)
    shootouts = martj42.parse_shootouts(shootouts_text)
    match_odds = football_data.parse_workbook(workbook)
    elo_tsv = latest_elo_tsv(settings.data_dir / "ratings")
    teams = build_team_dimension(settings.data_dir, elo_tsv=elo_tsv, matches=matches)
    closes_dir = settings.data_dir / "odds"
    ArtifactStore(settings).sync_down(prefix=ODDS_CLOSE.prefix, into=closes_dir)
    closes, outright_closes = market_closes.load_closes(closes_dir)
    elo_years = elo_history.load_elo_history(settings.data_dir / "ratings")

    manifest = write_dataset(
        out_dir,
        tables={
            "matches": _frame(matches, MatchRecord),
            "shootouts": _frame(shootouts, ShootoutRecord),
            "match_odds": _frame(match_odds, MatchOddsRecord),
            "teams": _frame(teams, TeamRecord),
            "market_closes": _frame(closes, ClosingOddsRecord),
            "outright_closes": _frame(outright_closes, OutrightCloseRecord),
            "elo_history": _frame(elo_years, EloHistoryRecord),
        },
        hashes={
            "martj42_results": _sha256(results_text),
            "martj42_shootouts": _sha256(shootouts_text),
            "football_data_internationals": _sha256(workbook),
            "elo_snapshot": _sha256(elo_tsv.read_bytes()),
            "market_closes": _dir_sha256(closes_dir),
        },
    )
    logger.info("dataset %s built: %s", manifest.dataset_id, manifest.tables)
    return manifest


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Build and publish the research dataset")
    add_storage_argument(parser)
    args = parser.parse_args()
    settings = apply_storage_choice(Settings(), args.storage)
    out_dir = settings.runs_root / "datasets"
    manifest = asyncio.run(build_dataset(settings, out_dir=out_dir))
    logger.info("manifest: %s", manifest.model_dump_json())
    DatasetStore(settings).publish(out_dir, manifest)


if __name__ == "__main__":
    main()
