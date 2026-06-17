"""Transfermarkt national-team squad pages, parsed to typed player records.

Regex extraction is deliberate: the repo carries no HTML parser dependency,
the page structure is pinned by a fixture test, and the pull script that
feeds this module runs by hand a handful of times per tournament."""

from __future__ import annotations

import re

from pydantic import BaseModel

_ROW_SPLIT = re.compile(r'<tr class="(?:odd|even)">')
_PLAYER_LINK = re.compile(r'href="/[^"]*/profil/spieler/(\d+)"\s*>\s*([^<]+?)\s*<')
_POSITION = re.compile(r"<tr>\s*<td[^>]*>\s*([^<]+?)\s*</td>\s*</tr>\s*</table>")
_POSITION_CELL = re.compile(r'class="zentriert rueckennummer bg_(\w+)"')
_SHIRT_NUMBER = re.compile(r"rn_nummer>([^<]*)</div>")
_VALUE_CELL = re.compile(r'<td class="rechts hauptlink">(.*?)</td>', re.S)
_TAGS = re.compile(r"<[^>]+>")
_VALUE_TEXT = re.compile(r"^€([\d.,]+)(m|k|bn)$")

POSITION_GROUPS = {"Torwart": "GK", "Abwehr": "DF", "Mittelfeld": "MF", "Sturm": "FW"}


class SquadPageParseError(Exception):
    def __init__(self, team_id: str, detail: str) -> None:
        self.team_id = team_id
        self.detail = detail
        super().__init__(f"squad page for {team_id!r}: {detail}")


class TransfermarktPlayer(BaseModel):
    name: str
    position: str
    position_group: str
    shirt_number: int | None
    value_eur_m: float | None
    transfermarkt_id: int


def parse_value_eur_m(text: str) -> float | None:
    """EUR millions from a Transfermarkt value string: '€25.00m', '€950k', '-' (no estimate)."""
    if text == "-":
        return None
    match = _VALUE_TEXT.match(text.replace(",", ""))
    if match is None:
        raise ValueError(f"unparseable market value {text!r}")
    amount = float(match.group(1))
    return {"m": amount, "k": amount / 1000, "bn": amount * 1000}[match.group(2)]


def parse_squad_page(html: str, *, team_id: str) -> list[TransfermarktPlayer]:
    """Extract the squad table of a kader/verein/{id}/plus/1 page."""
    players: list[TransfermarktPlayer] = []
    for chunk in _ROW_SPLIT.split(html)[1:]:
        link = _PLAYER_LINK.search(chunk)
        if link is None:
            raise SquadPageParseError(team_id, "row without a player profile link")
        name = link.group(2)
        position = _require(_POSITION, chunk, team_id, f"position for {name}").group(1)
        group_key = _require(_POSITION_CELL, chunk, team_id, f"position group for {name}").group(1)
        if group_key not in POSITION_GROUPS:
            raise SquadPageParseError(team_id, f"unknown position group {group_key!r} for {name}")
        shirt_raw = _require(_SHIRT_NUMBER, chunk, team_id, f"shirt number cell for {name}").group(1).strip()
        value_cell = _TAGS.sub("", _require(_VALUE_CELL, chunk, team_id, f"value cell for {name}").group(1)).strip()
        try:
            value = parse_value_eur_m(value_cell)
        except ValueError as exc:
            raise SquadPageParseError(team_id, f"{exc} for {name}") from exc
        players.append(
            TransfermarktPlayer(
                name=name,
                position=position,
                position_group=POSITION_GROUPS[group_key],
                shirt_number=int(shirt_raw) if shirt_raw.isdigit() else None,
                value_eur_m=value,
                transfermarkt_id=int(link.group(1)),
            )
        )
    if not players:
        raise SquadPageParseError(team_id, "no squad rows found")
    return players


def _require(pattern: re.Pattern[str], chunk: str, team_id: str, what: str) -> re.Match[str]:
    match = pattern.search(chunk)
    if match is None:
        raise SquadPageParseError(team_id, f"missing {what}")
    return match
