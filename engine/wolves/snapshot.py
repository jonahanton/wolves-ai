from __future__ import annotations

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class Candidate(BaseModel):
    team_id: str
    prob: float


class SlotSide(BaseModel):
    label: str
    candidates: list[Candidate]


class Slot(BaseModel):
    match: int
    stage: str
    date: str
    city: str
    home: SlotSide
    away: SlotSide


class RoundOpponents(BaseModel):
    """Opponent distribution for a later round, conditional on the group finish and England reaching it."""

    round: str
    match: int
    city: str
    date: str
    reach_prob: float
    opponents: list[Candidate]


class EnglandPath(BaseModel):
    finish: str
    prob: float
    r32_match: int
    city: str
    date: str
    opponents: list[Candidate]
    onward: list[RoundOpponents] = Field(default_factory=list)


class ModalStep(BaseModel):
    round: str
    match: int
    city: str
    date: str
    opponent_id: str
    opponent_prob: float


class CityProb(BaseModel):
    city: str
    prob: float


class LockDate(BaseModel):
    """How certain England's R32 city is once a group matchday completes; bookability signal."""

    date: str
    prob_locked: float
    locked_city_probs: dict[str, float]


class WhatIfOutcome(BaseModel):
    outcome: str
    prob: float
    finish_probs: dict[str, float]
    r32_city_probs: dict[str, float]


class WhatIfFixture(BaseModel):
    match: int
    date: str
    city: str
    opponent_id: str
    outcomes: list[WhatIfOutcome]


class EnglandBlock(BaseModel):
    team_id: str
    group: str
    finish_probs: dict[str, float]
    reach_probs: dict[str, float]
    paths: list[EnglandPath]
    modal_path: list[ModalStep] = Field(default_factory=list)
    city_probs: dict[str, list[CityProb]] = Field(default_factory=dict)
    lock_dates: list[LockDate] = Field(default_factory=list)
    what_if: list[WhatIfFixture] = Field(default_factory=list)


class RunMeta(BaseModel):
    run_id: str
    created_at: str
    n_sims: int
    engine_version: str
    kind: str


class TeamInfo(BaseModel):
    team_id: str
    name: str
    group: str
    elo: float
    rating: float = 0.0
    value_eur_m: float | None = None
    champion_prob: float = 0.0


class Snapshot(BaseModel):
    """The engine-to-web contract; additive changes only, breaking changes bump SCHEMA_VERSION."""

    schema_version: int = SCHEMA_VERSION
    run: RunMeta
    england: EnglandBlock
    slots: list[Slot]
    teams: list[TeamInfo]
