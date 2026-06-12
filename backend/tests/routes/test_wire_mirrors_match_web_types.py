"""Pins the web TS mirrors to the backend wire models by parsing the TS source."""

from __future__ import annotations

import re

from pydantic.alias_generators import to_camel

from wolves import live_state
from wolves_backend import models
from wolves_backend.config import REPO_ROOT

WEB_LIB = REPO_ROOT / "web" / "src" / "lib"


def _ts_interface_fields(source: str, name: str) -> set[str]:
    match = re.search(rf"export interface {name}\s*{{(.*?)}}", source, re.S)
    assert match, f"interface {name} not found"
    return {field_match.group(1) for field_match in re.finditer(r"^\s{2}(\w+)\??:", match.group(1), re.M)}


def test_live_mirrors_carry_the_wire_field_names():
    source = (WEB_LIB / "live.ts").read_text(encoding="utf-8")
    engine_owned = ["LiveForecast", "LiveFixture", "ScheduleDrift", "LiveState"]
    backend_owned = ["LiveHistoryPoint", "LiveHistoryFixture", "LiveHistory"]
    for name in engine_owned + backend_owned:
        owner = live_state if name in engine_owned else models
        wire = set(getattr(owner, name).model_fields)
        assert _ts_interface_fields(source, name) == wire, f"{name} drifted"


def test_run_mirrors_carry_the_camel_cased_wire_names():
    source = (WEB_LIB / "runs.ts").read_text(encoding="utf-8")
    for name in ["RunRecord", "SnapshotRef", "TeamHistoryPoint", "TeamHistory"]:
        wire = {to_camel(field) for field in getattr(models, name).model_fields}
        assert _ts_interface_fields(source, name) == wire, f"{name} drifted"
