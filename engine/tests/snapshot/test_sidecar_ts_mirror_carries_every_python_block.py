from __future__ import annotations

import re
from pathlib import Path

import pytest

from wolves.sidecars import (
    BracketSample,
    BracketSampleMatch,
    BracketSamples,
    MatchWdl,
    MatchWdlDraws,
    OpponentProb,
    PairingMatrices,
)

TS_SOURCE = (Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "sidecars.ts").read_text(encoding="utf-8")

MODELS = (BracketSamples, BracketSample, BracketSampleMatch, PairingMatrices, OpponentProb, MatchWdlDraws, MatchWdl)


def _ts_has_field(name: str) -> bool:
    return bool(re.search(rf"\b{re.escape(name)}\??\s*:", TS_SOURCE))


@pytest.mark.parametrize("model", MODELS)
def test_every_field_appears_in_the_ts_mirror(model) -> None:
    missing = [name for name in model.model_fields if not _ts_has_field(name)]
    assert not missing, f"{model.__name__} fields missing from sidecars.ts: {missing}"


def test_sidecar_interfaces_exist() -> None:
    for model in MODELS:
        assert f"export interface {model.__name__}" in TS_SOURCE
