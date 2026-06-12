"""Pull the 48 Transfermarkt national-team squad pages into a dated
data/ratings/squad-players-<date>.json, rewrite the derived squad-values.json
totals, and mirror the dated file to the bucket. Run by hand after a squad
change or a Transfermarkt revaluation wave; never on a schedule.

Fallback if Transfermarkt blocks this machine: the weekly Kaggle dump
(kaggle datasets download davidcariboo/player-scores), joined on player name,
accepting null values for players in uncovered leagues."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx

from wolves.config import Settings
from wolves.data.sources.squad_players import load_squad_players, team_totals
from wolves.data.sources.transfermarkt import TransfermarktPlayer, parse_squad_page
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import SQUAD_PLAYERS

logger = logging.getLogger("pull_squad_values")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SQUAD_URL = "https://www.transfermarkt.com/{team}/kader/verein/{verein_id}/plus/1"
# A human pace and an honest browser UA: one polite pass over 48 public pages.
REQUEST_DELAY_S = 4.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ANNOUNCED_SQUAD_SIZE = 26


class TeamIdMapMismatchError(Exception):
    def __init__(self, missing: set[str], extra: set[str]) -> None:
        self.missing = missing
        self.extra = extra
        super().__init__(f"transfermarkt-team-ids.json missing {sorted(missing)}, extra {sorted(extra)}")


def verein_ids() -> dict[str, int]:
    ids: dict[str, int] = json.loads((DATA_DIR / "ratings" / "transfermarkt-team-ids.json").read_text())["vereinIds"]
    registry = {entry["id"] for entry in json.loads((DATA_DIR / "format" / "teams.json").read_text())}
    if set(ids) != registry:
        raise TeamIdMapMismatchError(registry - set(ids), set(ids) - registry)
    return ids


async def fetch_squads(ids: dict[str, int]) -> dict[str, list[TransfermarktPlayer]]:
    squads: dict[str, list[TransfermarktPlayer]] = {}
    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for team, verein_id in ids.items():
            response = await client.get(SQUAD_URL.format(team=team, verein_id=verein_id))
            response.raise_for_status()
            players = parse_squad_page(response.text, team_id=team)
            nulls = sum(player.value_eur_m is None for player in players)
            level = logging.WARNING if len(players) != ANNOUNCED_SQUAD_SIZE or nulls else logging.INFO
            logger.log(level, "%s: %d players, %d without a value estimate", team, len(players), nulls)
            squads[team] = players
            await asyncio.sleep(REQUEST_DELAY_S)
    return squads


def write_players_file(squads: dict[str, list[TransfermarktPlayer]], *, as_of: str) -> Path:
    payload = {
        "asOf": as_of,
        "source": "transfermarkt national-team squad pages (kader/verein, current squad view)",
        "players": [
            {
                "team": team,
                "name": player.name,
                "position": player.position,
                "positionGroup": player.position_group,
                "shirtNumber": player.shirt_number,
                "valueEurM": player.value_eur_m,
                "transfermarktId": player.transfermarkt_id,
            }
            for team, players in squads.items()
            for player in players
        ],
    }
    path = DATA_DIR / "ratings" / f"squad-players-{as_of}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def rewrite_totals(*, as_of: str) -> None:
    totals = team_totals(load_squad_players(DATA_DIR / "ratings"))
    payload = {
        "asOf": as_of,
        "source": f"sum of squad-players-{as_of}.json per team, Transfermarkt values, EUR millions",
        "valuesEurM": dict(sorted(totals.items())),
    }
    (DATA_DIR / "ratings" / "squad-values.json").write_text(
        json.dumps(payload, indent=1) + "\n", encoding="utf-8"
    )


def mirror_to_s3(players_path: Path, *, as_of: str) -> None:
    settings = Settings()
    if settings.storage_mode == "local" or not settings.bucket:
        logger.warning("cloud storage off; %s exists in git and on this machine only", players_path.name)
        return
    store = ArtifactStore(settings.model_copy(update={"storage_mode": "s3"}))
    store.put(SQUAD_PLAYERS, players_path.read_text(encoding="utf-8"), date=as_of)
    logger.info("mirrored %s", SQUAD_PLAYERS.key(date=as_of))


async def main() -> None:
    configure_cli_logging()
    as_of = datetime.now(UTC).date().isoformat()
    squads = await fetch_squads(verein_ids())
    players_path = write_players_file(squads, as_of=as_of)
    rewrite_totals(as_of=as_of)
    logger.info("wrote %s and derived squad-values.json", players_path.name)
    mirror_to_s3(players_path, as_of=as_of)


if __name__ == "__main__":
    asyncio.run(main())
