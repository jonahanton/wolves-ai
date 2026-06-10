"""The match-model contract: fit freezes everything learned from the dataset,
score_distribution maps any fixture to a typed scoreline grid."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

import numpy as np

MAX_GOALS = 10


def module_version(module_file: str) -> str:
    """12-hex sha of the module source: the version changes exactly when the code can."""
    return hashlib.sha256(Path(module_file).read_bytes()).hexdigest()[:12]


class UnknownModelTeamError(Exception):
    """A fixture references a team the fitted state has no parameters for."""

    def __init__(self, team: str, model_id: str) -> None:
        self.team = team
        self.model_id = model_id
        super().__init__(f"model {model_id!r} has no parameters for team {team!r}")


@dataclass(frozen=True)
class DatasetHandle:
    """A built dataset on local disk, pinned by version."""

    path: Path
    version: str


@dataclass(frozen=True)
class Fixture:
    home: str
    away: str
    neutral: bool = True


@dataclass(frozen=True)
class ScorelineDistribution:
    """Normalised grid where grid[h, a] = P(home scores h, away scores a)."""

    grid: np.ndarray

    def __post_init__(self) -> None:
        self.grid.setflags(write=False)

    @property
    def p_home(self) -> float:
        return float(np.tril(self.grid, -1).sum())

    @property
    def p_draw(self) -> float:
        return float(np.trace(self.grid))

    @property
    def p_away(self) -> float:
        return float(np.triu(self.grid, 1).sum())

    def outcome_probs(self) -> tuple[float, float, float]:
        return self.p_home, self.p_draw, self.p_away

    def sample(self, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
        """Draw n scorelines; returns (home_goals, away_goals) int arrays."""
        side = self.grid.shape[0]
        flat = rng.choice(side * side, size=n, p=self.grid.ravel())
        return flat // side, flat % side


@dataclass(frozen=True)
class FittedState:
    """Frozen fit output; deterministic given (dataset version, as_of, seed)."""

    model_id: str
    version: str
    dataset_version: str
    as_of: date
    teams: tuple[str, ...]
    strengths: np.ndarray
    globals_: dict[str, float] = field(default_factory=dict)
    covariance: np.ndarray | None = None
    diagnostics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.strengths.setflags(write=False)
        if self.covariance is not None:
            self.covariance.setflags(write=False)

    def strength_of(self, team: str) -> float:
        try:
            return float(self.strengths[self.teams.index(team)])
        except ValueError as exc:
            raise UnknownModelTeamError(team, self.model_id) from exc


class MatchModel(Protocol):
    """Pure by contract: no I/O beyond the dataset in fit, no unseeded randomness."""

    model_id: str
    version: str

    def fit(self, dataset: DatasetHandle, *, as_of: date, seed: int = 0) -> FittedState: ...

    def score_distribution(
        self, fixture: Fixture, state: FittedState, *, intensity: float = 1.0
    ) -> ScorelineDistribution: ...
