from __future__ import annotations

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.retrieval.web_search import WebSearchArgs, _web_search


async def test_web_search_refuses_future_dates_after_as_of(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"

    result = await _web_search(WebSearchArgs(query="England injury news June 15 16"), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "future_date_query"
    assert "June 15" in result.error.message
    deps.runtime.shutdown()


async def test_web_search_allows_as_of_date(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-14"

    with deps.runtime.run_trace():
        result = await _web_search(WebSearchArgs(query="World Cup standings June 14 2026"), deps)

    assert result.ok
    deps.runtime.shutdown()
