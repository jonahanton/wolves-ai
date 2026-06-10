"""Year-end eloratings.net snapshots: the shrinkage covariate for model fits.
A fit as_of date may only use the snapshot from the prior year end."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from wolves.data.teams import canonical_team_key


class EloHistoryRecord(BaseModel):
    year: int
    team: str
    elo: float


def _names_by_code(codes_path: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    for line in codes_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names[parts[0]] = parts[1]
    return names


def load_elo_history(ratings_dir: Path) -> list[EloHistoryRecord]:
    names = _names_by_code(ratings_dir / "elo-team-codes.tsv")
    records: list[EloHistoryRecord] = []
    for path in sorted((ratings_dir / "history").glob("elo-*.tsv")):
        year = int(path.stem.removeprefix("elo-"))
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) > 3 and parts[2] in names:
                records.append(
                    EloHistoryRecord(year=year, team=canonical_team_key(names[parts[2]]), elo=float(parts[3]))
                )
    return records
