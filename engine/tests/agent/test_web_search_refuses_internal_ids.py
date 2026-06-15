from __future__ import annotations

from pathlib import Path

import pytest

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.retrieval.web_search import WebSearchArgs, _web_search


@pytest.fixture
def deps(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    yield deps
    deps.runtime.shutdown()


async def test_internal_run_ids_are_not_web_search_terms(deps):
    result = await _web_search(
        WebSearchArgs(query="scn-001 scn-002 goalkeeper scenarios World Cup 2026"),
        deps,
    )

    assert not result.ok
    assert result.error.type == "internal_id_query"


async def test_internal_scenario_names_are_not_web_search_terms(deps):
    result = await _web_search(
        WebSearchArgs(query="keeper_watch_2026-06-13 goalkeeper World Cup 2026"),
        deps,
    )

    assert not result.ok
    assert result.error.type == "internal_id_query"


async def test_ledger_and_live_snapshot_ids_are_not_web_search_terms(deps):
    result = await _web_search(
        WebSearchArgs(query="led-0001 live-20260613-210542 England evidence"),
        deps,
    )

    assert not result.ok
    assert result.error.type == "internal_id_query"


async def test_retrieval_artifact_ids_are_not_web_search_terms(deps):
    result = await _web_search(
        WebSearchArgs(query="retrieval-001 England injury relevance"),
        deps,
    )

    assert not result.ok
    assert result.error.type == "internal_id_query"
