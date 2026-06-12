from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import NodePatch
from wolves.graph.nodes import _bounded

BRIEF = NodePatch(node_id="forecast-1", kind="forecast", objective="submit", brief="submit")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        runs_root=tmp_path,
        storage_mode="local",
        graph_forecast_timeout_s=1,
        graph_forecast_grace_s=1,
    )


async def _run_for(seconds: float) -> str:
    await asyncio.sleep(seconds)
    return "done"


async def test_mid_steelman_timeout_gets_one_grace_window(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.submission.escalation_fired = True

    result = await _bounded(_run_for(1.4), brief=BRIEF, deps=deps, settings=_settings(tmp_path))
    deps.runtime.shutdown()
    assert result == "done"


@pytest.mark.parametrize("escalation_fired", [False, True], ids=["no-steelman-no-grace", "grace-is-bounded"])
async def test_timeout_still_kills_the_node(tmp_path: Path, escalation_fired: bool):
    deps = build_graph_deps(tmp_path)
    deps.submission.escalation_fired = escalation_fired

    with pytest.raises(TimeoutError):
        await _bounded(_run_for(10), brief=BRIEF, deps=deps, settings=_settings(tmp_path))
    deps.runtime.shutdown()
