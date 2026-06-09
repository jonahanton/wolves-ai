from __future__ import annotations

from pathlib import Path

import numpy as np

from wolves.sim.format import FormatData


class RatingNotFoundError(Exception):
    def __init__(self, elo_code: str) -> None:
        self.elo_code = elo_code
        super().__init__(f"no Elo rating for code {elo_code!r}")


def load_elo_ratings(tsv_path: Path, fmt: FormatData) -> np.ndarray:
    """Parse an eloratings.net World.tsv into a rating vector aligned with fmt.teams."""
    by_code: dict[str, float] = {}
    for line in tsv_path.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) > 3:
            by_code[parts[2]] = float(parts[3])
    ratings = np.empty(len(fmt.teams), dtype=np.float64)
    for i, team in enumerate(fmt.teams):
        if team.elo_code not in by_code:
            raise RatingNotFoundError(team.elo_code)
        ratings[i] = by_code[team.elo_code]
    return ratings
