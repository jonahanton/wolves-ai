from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from wolves.config import Settings

GROUPS = "ABCDEFGHIJKL"


class Team(BaseModel):
    id: str
    name: str
    group: str
    elo_code: str


class GroupMatch(BaseModel):
    match: int
    group: str
    date: str
    city: str
    home: str
    away: str


class KnockoutMatch(BaseModel):
    """Home/away are slot specs: '1A', '2K', '3:EHIJK', 'W80' or 'L101'."""

    match: int
    stage: str
    date: str
    city: str
    home: str
    away: str


class Venue(BaseModel):
    city: str
    stadium: str
    country: str
    altitude_m: int
    roofed: bool
    lat: float
    lon: float


class PlayedResult(BaseModel):
    """A completed match overlaid on the simulation; winner disambiguates knockout draws."""

    match: int
    home_goals: int
    away_goals: int
    winner: str | None = None


class FormatData(BaseModel):
    teams: list[Team]
    group_matches: list[GroupMatch]
    knockout: list[KnockoutMatch]
    venues: list[Venue]

    def team_index(self) -> dict[str, int]:
        return {t.id: i for i, t in enumerate(self.teams)}

    def group_members(self) -> dict[str, list[int]]:
        idx = self.team_index()
        members: dict[str, list[int]] = {g: [] for g in GROUPS}
        for t in self.teams:
            members[t.group].append(idx[t.id])
        return members

    def venue_by_city(self) -> dict[str, Venue]:
        return {v.city: v for v in self.venues}


def load_format(data_dir: Path) -> FormatData:
    """Load the static tournament format from data/format."""
    teams_raw = json.loads((data_dir / "format" / "teams.json").read_text())
    schedule = json.loads((data_dir / "format" / "schedule.json").read_text())
    venues_raw = json.loads((data_dir / "format" / "venues.json").read_text())
    teams = [Team(id=t["id"], name=t["name"], group=t["group"], elo_code=t["eloCode"]) for t in teams_raw]
    venues = [
        Venue(
            city=v["city"],
            stadium=v["stadium"],
            country=v["country"],
            altitude_m=v["altitudeM"],
            roofed=v["roofed"],
            lat=v["lat"],
            lon=v["lon"],
        )
        for v in venues_raw
    ]
    return FormatData(
        teams=teams,
        group_matches=[GroupMatch(**m) for m in schedule["groupMatches"]],
        knockout=[KnockoutMatch(**m) for m in schedule["knockout"]],
        venues=venues,
    )


def load_results(data_dir: Path, *, settings: Settings | None = None) -> dict[int, PlayedResult]:
    """Played results keyed by match number: the static file unioned with
    results persisted from live polling, the persisted side winning."""
    # Imported lazily: results_store needs PlayedResult from this module.
    from wolves.config import get_settings
    from wolves.sim.results_store import persisted_results

    raw = json.loads((data_dir / "results.json").read_text())
    results = [
        PlayedResult(match=r["match"], home_goals=r["homeGoals"], away_goals=r["awayGoals"], winner=r.get("winner"))
        for r in raw["results"]
    ]
    return {r.match: r for r in results} | persisted_results(settings or get_settings())
