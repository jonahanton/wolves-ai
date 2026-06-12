from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MatchRecord(BaseModel):
    """One full international from the martj42 results backbone."""

    date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    tournament: str
    importance: float
    neutral: bool


class ShootoutRecord(BaseModel):
    date: date
    home_team: str
    away_team: str
    winner: str


class MatchOddsRecord(BaseModel):
    """One bookmaker's 1X2 prices for one tournament match."""

    competition: str
    date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    bookmaker: str
    home_price: float
    draw_price: float
    away_price: float


class TeamRecord(BaseModel):
    """Dataset team key joined to the 2026 registry and covariates where known."""

    team: str
    app_team_id: str | None = None
    elo: float | None = None
    squad_value_eur_m: float | None = None


class SquadPlayerRecord(BaseModel):
    """One announced-squad player with the Transfermarkt crowd valuation."""

    team: str
    app_team_id: str
    name: str
    position: str
    position_group: str
    shirt_number: int | None = None
    value_eur_m: float | None = None
    transfermarkt_id: int
    as_of: date


class DatasetManifest(BaseModel):
    dataset_id: str
    built_at: str
    engine_version: str
    tables: dict[str, int]
    source_hashes: dict[str, str]
