"""Authoritative final squad lists keyed by app team id.

Names only: the per-player valuations and team totals live in
squad-players-*.json and squad-values.json. This file exists because the
Transfermarkt pull occasionally diverges from the announced 26 (naming
variants, late swaps), and narrative roster validation needs the official
list, not the valuation source."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROSTERS_FILENAME = "squad-rosters-2026.json"


class SquadRostersFileMissingError(Exception):
    def __init__(self, ratings_dir: Path) -> None:
        self.ratings_dir = ratings_dir
        super().__init__(f"no {ROSTERS_FILENAME} under {ratings_dir}")


def load_rosters(ratings_dir: Path) -> dict[str, list[str]]:
    """Player names per app team id from the authoritative roster file."""
    path = ratings_dir / ROSTERS_FILENAME
    if not path.exists():
        raise SquadRostersFileMissingError(ratings_dir)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {team: entry["players"] for team, entry in payload["rosters"].items()}


def _name_tokens(name: str) -> set[str]:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return {part for part in ascii_name.lower().replace("-", " ").split() if len(part) > 1}


def roster_name_tokens(ratings_dir: Path) -> frozenset[str]:
    """Every accent-stripped name token across all authoritative rosters."""
    tokens: set[str] = set()
    for players in load_rosters(ratings_dir).values():
        for name in players:
            tokens |= _name_tokens(name)
    return frozenset(tokens)
