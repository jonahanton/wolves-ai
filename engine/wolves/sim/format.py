from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

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


class FormatData(BaseModel):
    teams: list[Team]
    group_matches: list[GroupMatch]
    knockout: list[KnockoutMatch]

    def team_index(self) -> dict[str, int]:
        return {t.id: i for i, t in enumerate(self.teams)}

    def group_members(self) -> dict[str, list[int]]:
        idx = self.team_index()
        members: dict[str, list[int]] = {g: [] for g in GROUPS}
        for t in self.teams:
            members[t.group].append(idx[t.id])
        return members


def load_format(data_dir: Path) -> FormatData:
    """Load the static tournament format from data/format."""
    teams_raw = json.loads((data_dir / "format" / "teams.json").read_text())
    schedule = json.loads((data_dir / "format" / "schedule.json").read_text())
    teams = [Team(id=t["id"], name=t["name"], group=t["group"], elo_code=t["eloCode"]) for t in teams_raw]
    return FormatData(
        teams=teams,
        group_matches=[GroupMatch(**m) for m in schedule["groupMatches"]],
        knockout=[KnockoutMatch(**m) for m in schedule["knockout"]],
    )
