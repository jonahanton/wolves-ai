"""Per-player squad valuations from the dated Transfermarkt pull files.

The team totals in squad-values.json are derived from these records; the
aggregation rule lives here so the pull script and the parity gate cannot
drift apart."""

from __future__ import annotations

import json
import unicodedata
from datetime import date
from pathlib import Path

from wolves.data.contracts import SquadPlayerRecord
from wolves.data.teams import registry_team_key

IMPUTE_NULLS_ABOVE = 3


class SquadPlayersFileMissingError(Exception):
    def __init__(self, ratings_dir: Path) -> None:
        self.ratings_dir = ratings_dir
        super().__init__(f"no squad-players-*.json under {ratings_dir}")


def latest_players_file(ratings_dir: Path) -> Path:
    candidates = sorted(ratings_dir.glob("squad-players-*.json"))
    if not candidates:
        raise SquadPlayersFileMissingError(ratings_dir)
    return candidates[-1]


def load_squad_players(ratings_dir: Path) -> list[SquadPlayerRecord]:
    """Read the latest dated pull into records keyed for the dataset join."""
    payload = json.loads(latest_players_file(ratings_dir).read_text(encoding="utf-8"))
    as_of = date.fromisoformat(payload["asOf"])
    return [
        SquadPlayerRecord(
            team=registry_team_key(player["team"]),
            app_team_id=player["team"],
            name=player["name"],
            position=player["position"],
            position_group=player["positionGroup"],
            shirt_number=player["shirtNumber"],
            value_eur_m=player["valueEurM"],
            transfermarkt_id=player["transfermarktId"],
            as_of=as_of,
        )
        for player in payload["players"]
    ]


def _name_tokens(name: str) -> set[str]:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return {part for part in ascii_name.lower().replace("-", " ").split() if len(part) > 1}


def roster_name_tokens(records: list[SquadPlayerRecord]) -> frozenset[str]:
    """Every accent-stripped, lowercased name token across all squads, so a
    surname in published copy can be cross-checked against the rosters."""
    tokens: set[str] = set()
    for record in records:
        tokens |= _name_tokens(record.name)
    return frozenset(tokens)


def team_totals(records: list[SquadPlayerRecord]) -> dict[str, float]:
    """Squad value per app team id: sum of non-null player values, EUR millions.

    A team with more than IMPUTE_NULLS_ABOVE unvalued players gets each null
    imputed at the squad's minimum observed value, so a sparsely covered
    federation is not shipped a distorted total."""
    by_team: dict[str, list[float | None]] = {}
    for record in records:
        by_team.setdefault(record.app_team_id, []).append(record.value_eur_m)
    totals: dict[str, float] = {}
    for team, values in by_team.items():
        known = [value for value in values if value is not None]
        nulls = len(values) - len(known)
        imputed = min(known) * nulls if nulls > IMPUTE_NULLS_ABOVE else 0.0
        totals[team] = round(sum(known) + imputed, 1)
    return totals
