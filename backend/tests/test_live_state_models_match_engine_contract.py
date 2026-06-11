"""Pins the backend's LiveState wire models and live key to the engine's,
parsing the engine source via ast because the backend venv lacks engine deps."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from wolves_backend import models
from wolves_backend.config import REPO_ROOT
from wolves_backend.routes.live import LIVE_STATE_KEY

ENGINE_LIVE_STATE = REPO_ROOT / "engine" / "wolves" / "live_state.py"
ENGINE_LAYOUT = REPO_ROOT / "engine" / "wolves" / "s3" / "layout.py"


def _engine_model_fields(source_path: Path, class_name: str) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    raise AssertionError(f"{class_name} not found in {source_path}")


@pytest.mark.parametrize("class_name", ["LiveForecast", "LiveFixture", "ScheduleDrift", "LiveState"])
def test_backend_live_models_carry_the_engine_fields(class_name):
    engine_fields = _engine_model_fields(ENGINE_LIVE_STATE, class_name)
    backend_fields = set(getattr(models, class_name).model_fields)
    assert backend_fields == engine_fields, (
        f"{class_name} drifted: missing from backend {sorted(engine_fields - backend_fields)}, "
        f"missing from engine {sorted(backend_fields - engine_fields)}"
    )


def test_live_route_key_matches_the_engine_layout():
    tree = ast.parse(ENGINE_LAYOUT.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "LIVE_STATE"
            and isinstance(node.value, ast.Call)
        ):
            pattern = next(
                keyword.value.value
                for keyword in node.value.keywords
                if keyword.arg == "pattern" and isinstance(keyword.value, ast.Constant)
            )
            assert pattern == LIVE_STATE_KEY
            return
    raise AssertionError(f"LIVE_STATE not found in {ENGINE_LAYOUT}")
