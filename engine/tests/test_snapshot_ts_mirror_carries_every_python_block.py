from __future__ import annotations

from pathlib import Path

import pytest

from wolves.snapshot import ChampionBlock, MarketsBlock, Snapshot, TeamInterval

TS_SOURCE = (Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "snapshot.ts").read_text(encoding="utf-8")


@pytest.mark.parametrize("model", [Snapshot, ChampionBlock, TeamInterval, MarketsBlock])
def test_every_field_appears_in_the_ts_mirror(model) -> None:
    missing = [name for name in model.model_fields if name != "model_config" and f"{name}" not in TS_SOURCE]
    assert not missing, f"{model.__name__} fields missing from snapshot.ts: {missing}"


def test_block_interfaces_exist() -> None:
    for interface in ("ChampionBlock", "TeamInterval", "MarketsBlock"):
        assert f"export interface {interface}" in TS_SOURCE
