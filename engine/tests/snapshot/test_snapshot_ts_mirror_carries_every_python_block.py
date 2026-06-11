from __future__ import annotations

import re
from pathlib import Path

import pytest

from wolves.snapshot import ChampionBlock, MarketsBlock, Snapshot, TeamInterval

TS_SOURCE = (Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "snapshot.ts").read_text(encoding="utf-8")


def _ts_has_field(name: str) -> bool:
    return bool(re.search(rf"\b{re.escape(name)}\??\s*:", TS_SOURCE))


@pytest.mark.parametrize("model", [Snapshot, ChampionBlock, TeamInterval, MarketsBlock])
def test_every_field_appears_in_the_ts_mirror(model) -> None:
    missing = [name for name in model.model_fields if not _ts_has_field(name)]
    assert not missing, f"{model.__name__} fields missing from snapshot.ts: {missing}"


def test_block_interfaces_exist() -> None:
    for interface in ("ChampionBlock", "TeamInterval", "MarketsBlock"):
        assert f"export interface {interface}" in TS_SOURCE
