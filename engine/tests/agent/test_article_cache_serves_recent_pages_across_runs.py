from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.article_cache import ArticleCache
from wolves.agent.source_memory import SourceMemory
from wolves.agent.tools.retrieval.web_fetch import WebFetchArgs, _web_fetch

_URL = "https://www.reuters.com/keeper-fit"


def _deps(tmp_path: Path):
    return dataclasses.replace(
        build_graph_deps(tmp_path),
        source_memory=SourceMemory(tmp_path / "agent-state" / "sources_seen.jsonl"),
        articles=ArticleCache(tmp_path / "agent-state" / "articles"),
    )


def _seed(cache: ArticleCache, *, age_hours: float) -> None:
    article = cache.put(url=_URL, final_url=_URL, title="Keeper fit", text="x" * 500, run_id="agent-yesterday")
    stamped = article.model_copy(
        update={"retrieved_at": (datetime.now(UTC) - timedelta(hours=age_hours)).isoformat(timespec="seconds")}
    )
    cache._path(_URL).write_text(stamped.model_dump_json(), encoding="utf-8")


async def test_fresh_cache_serves_with_provenance_and_backs_confirmed_claims(tmp_path: Path):
    deps = _deps(tmp_path)
    _seed(deps.articles, age_hours=6)

    with deps.runtime.run_trace():
        result = await _web_fetch(WebFetchArgs(url=_URL), deps)

    assert result.ok and result.payload["cached"]["run_id"] == "agent-yesterday"
    assert result.payload["cached"]["age_hours"] >= 6
    seen = deps.source_memory.seen(_URL)
    assert seen.last_seen_run == deps.runtime.run_id and seen.disposition == "fetched"
    deps.runtime.shutdown()


async def test_stale_cache_and_explicit_refresh_fetch_live(tmp_path: Path):
    stale_deps = _deps(tmp_path / "stale")
    _seed(stale_deps.articles, age_hours=72)
    fresh_deps = _deps(tmp_path / "fresh")
    _seed(fresh_deps.articles, age_hours=6)

    with stale_deps.runtime.run_trace():
        stale = await _web_fetch(WebFetchArgs(url=_URL), stale_deps)
    with fresh_deps.runtime.run_trace():
        refreshed = await _web_fetch(WebFetchArgs(url=_URL, refresh=True), fresh_deps)

    assert stale.ok and "cached" not in stale.payload
    assert refreshed.ok and "cached" not in refreshed.payload
    stale_deps.runtime.shutdown()
    fresh_deps.runtime.shutdown()
