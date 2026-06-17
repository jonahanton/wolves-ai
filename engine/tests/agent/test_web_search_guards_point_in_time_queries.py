from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.retrieval.web_search import WebSearchArgs, _web_search
from wolves.connectors import FakeSearchClient, ObservedWeb


async def test_web_search_rejects_private_run_handles(tmp_path: Path):
    deps = build_graph_deps(tmp_path)

    result = await _web_search(WebSearchArgs(query="agent-20260613-140248 scn-001 goalkeeper"), deps)
    deps.runtime.shutdown()

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "internal_id_query"
    assert "agent-20260613-140248" in result.error.message


async def test_web_search_defaults_to_as_of_boundary(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    brave = FakeSearchClient()
    deps = dataclasses.replace(deps, web=ObservedWeb(runtime=deps.runtime, brave=brave))

    with deps.runtime.run_trace(title="web search test"):
        result = await _web_search(WebSearchArgs(query="World Cup France squad news"), deps)
    deps.runtime.shutdown()

    assert result.ok
    assert brave.end_published_dates == ["2026-06-14"]


async def test_web_search_auto_uses_exa_when_search_is_not_freshness_bound(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    brave = FakeSearchClient(provider="brave")
    exa = FakeSearchClient(provider="exa")
    deps = dataclasses.replace(deps, web=ObservedWeb(runtime=deps.runtime, brave=brave, exa=exa))

    with deps.runtime.run_trace(title="web search test"):
        result = await _web_search(WebSearchArgs(query="World Cup contender injury context"), deps)
    deps.runtime.shutdown()

    assert result.ok
    assert result.payload["provider"] == "exa"
    assert exa.end_published_dates == ["2026-06-14"]
    assert brave.calls == []


async def test_web_search_explicit_exa_falls_back_to_brave_when_exa_is_unconfigured(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    brave = FakeSearchClient(provider="brave")
    deps = dataclasses.replace(deps, web=ObservedWeb(runtime=deps.runtime, brave=brave))

    with deps.runtime.run_trace(title="web search test"):
        result = await _web_search(WebSearchArgs(query="World Cup contender context", provider="exa"), deps)
    deps.runtime.shutdown()

    assert result.ok
    assert result.payload["requested_provider"] == "exa"
    assert result.payload["provider"] == "brave"


async def test_web_search_clamps_future_end_date_to_as_of(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"
    brave = FakeSearchClient()
    deps = dataclasses.replace(deps, web=ObservedWeb(runtime=deps.runtime, brave=brave))

    with deps.runtime.run_trace(title="web search test"):
        result = await _web_search(
            WebSearchArgs(query="World Cup France squad news", end_published_date="2026-06-15"),
            deps,
        )
    deps.runtime.shutdown()

    assert result.ok
    assert brave.end_published_dates == ["2026-06-14"]


async def test_web_search_rejects_invalid_end_date(tmp_path: Path):
    deps = build_graph_deps(tmp_path)

    result = await _web_search(
        WebSearchArgs(query="World Cup France squad news", end_published_date="tomorrow"),
        deps,
    )
    deps.runtime.shutdown()

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "invalid_arguments"
