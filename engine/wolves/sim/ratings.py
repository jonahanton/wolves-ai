from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wolves.sim.format import FormatData

VALUE_PRIOR_WEIGHT = 0.40


class RatingNotFoundError(Exception):
    def __init__(self, elo_code: str) -> None:
        self.elo_code = elo_code
        super().__init__(f"no Elo rating for code {elo_code!r}")


class SquadValueNotFoundError(Exception):
    def __init__(self, team_id: str) -> None:
        self.team_id = team_id
        super().__init__(f"no squad value for team {team_id!r}")


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


def load_squad_values(path: Path, fmt: FormatData) -> np.ndarray:
    """Load squad market values (EUR millions) aligned with fmt.teams."""
    by_id = json.loads(path.read_text())["valuesEurM"]
    values = np.empty(len(fmt.teams), dtype=np.float64)
    for i, team in enumerate(fmt.teams):
        if team.id not in by_id:
            raise SquadValueNotFoundError(team.id)
        values[i] = float(by_id[team.id])
    return values


def blend_value_prior(elo: np.ndarray, values: np.ndarray, *, weight: float = VALUE_PRIOR_WEIGHT) -> np.ndarray:
    """Shrink Elo toward a squad-value prior fitted as a least-squares line in log value."""
    design = np.column_stack([np.ones_like(values), np.log(values)])
    coef, *_ = np.linalg.lstsq(design, elo, rcond=None)
    return (1.0 - weight) * elo + weight * (design @ coef)
