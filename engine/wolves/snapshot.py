from __future__ import annotations

from pydantic import BaseModel

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


class EnglandPath(BaseModel):
    finish: str
    prob: float
    r32_match: int
    city: str
    date: str
    opponents: list[Candidate]


class EnglandBlock(BaseModel):
    team_id: str
    group: str
    finish_probs: dict[str, float]
    reach_probs: dict[str, float]
    paths: list[EnglandPath]


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


class Snapshot(BaseModel):
    """The engine-to-web contract; additive changes only, breaking changes bump SCHEMA_VERSION."""

    schema_version: int = SCHEMA_VERSION
    run: RunMeta
    england: EnglandBlock
    slots: list[Slot]
    teams: list[TeamInfo]
