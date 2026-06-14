"""The team page derives exit-stage and opponent-draw views by hand-writing the
knockout round chain in TypeScript. If the engine ever reorders or renames
KO_ROUNDS, those chains silently desync, so pin both against the engine here."""

from __future__ import annotations

import re
from pathlib import Path

from wolves.sidecars import KO_ROUNDS

WEB = Path(__file__).resolve().parents[3] / "web" / "src" / "lib"
REACH_TS = (WEB / "reach.ts").read_text(encoding="utf-8")
OPPONENTS_TS = (WEB / "opponents.ts").read_text(encoding="utf-8")


def _string_array(source: str, name: str) -> list[str]:
    match = re.search(rf"{name}\s*=\s*\[([^\]]*)\]", source)
    assert match is not None, f"{name} not found"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_opponent_stream_rounds_match_engine_ko_rounds() -> None:
    assert _string_array(OPPONENTS_TS, "STREAM_ROUNDS") == list(KO_ROUNDS)


def test_exit_stage_keys_extend_engine_rounds_with_groups_and_champion() -> None:
    keys = re.findall(r'key:\s*"([^"]+)"', REACH_TS)
    assert keys == ["groups", *KO_ROUNDS, "champion"]
