"""Every sidecar wire model has a field-complete TS mirror in sidecars.ts, and
every registered sidecar name is in the loader's SidecarName union. The
distributions sidecar (the per-world mixture decomposition) shipped served but
unmirrored once; this pins the whole registry against that recurring."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wolves.sidecars import SIDECARS
from wolves.sidecars import CellShape as _CellShape

TS_SOURCE = (Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "sidecars.ts").read_text(encoding="utf-8")

_MIRRORED_MODELS = [_CellShape, *(spec.model for spec in SIDECARS)]


def _ts_has_field(name: str) -> bool:
    return bool(re.search(rf"\b{re.escape(name)}\??\s*:", TS_SOURCE))


@pytest.mark.parametrize("model", _MIRRORED_MODELS, ids=lambda m: m.__name__)
def test_every_sidecar_field_appears_in_the_ts_mirror(model) -> None:
    missing = [name for name in model.model_fields if not _ts_has_field(name)]
    assert not missing, f"{model.__name__} fields missing from sidecars.ts: {missing}"


def test_every_registered_sidecar_name_is_in_the_loader_union() -> None:
    union = re.search(r"type SidecarName =([^;]+);", TS_SOURCE)
    assert union is not None
    declared = set(re.findall(r'"([^"]+)"', union.group(1)))
    assert {spec.name for spec in SIDECARS} == declared
