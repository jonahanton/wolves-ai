from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.article_cache import ArticleCache
from wolves.agent.source_memory import SourceMemory
from wolves.agent.tools.retrieval.web_fetch import WebFetchArgs, _web_fetch

_URL = "https://www.reuters.com/keeper-fit"
_FINAL_URL = "https://www.reuters.com/sports/soccer/keeper-fit"


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


def _seed_redirect(cache: ArticleCache, *, age_hours: float) -> None:
    article = cache.put(url=_URL, final_url=_FINAL_URL, title="Keeper fit", text="x" * 500, run_id="agent-yesterday")
    stamped = article.model_copy(
        update={"retrieved_at": (datetime.now(UTC) - timedelta(hours=age_hours)).isoformat(timespec="seconds")}
    )
    body = stamped.model_dump_json()
    cache._path(_URL).write_text(body, encoding="utf-8")
    cache._path(_FINAL_URL).write_text(body, encoding="utf-8")


def test_recent_uses_as_of_clock_for_backfilled_runs(tmp_path: Path):
    cache = ArticleCache(tmp_path / "agent-state" / "articles")
    article = cache.put(url=_URL, final_url=_URL, title="Keeper fit", text="x" * 500, run_id="agent-old")
    stamped = article.model_copy(update={"retrieved_at": "2026-06-01T12:00:00+00:00"})
    cache._path(_URL).write_text(stamped.model_dump_json(), encoding="utf-8")

    assert cache.recent(max_age_hours=48, as_of="2026-06-02")
    assert not cache.recent(max_age_hours=48, as_of="2026-06-10")


def test_get_refuses_articles_retrieved_after_as_of(tmp_path: Path):
    cache = ArticleCache(tmp_path / "agent-state" / "articles")
    article = cache.put(url=_URL, final_url=_URL, title="Keeper fit", text="x" * 500, run_id="agent-future")
    stamped = article.model_copy(update={"retrieved_at": "2026-06-15T12:00:00+00:00"})
    cache._path(_URL).write_text(stamped.model_dump_json(), encoding="utf-8")

    assert cache.get(_URL, as_of="2026-06-14") is None
    assert cache.get(_URL, as_of="2026-06-15") is not None


def test_get_keeps_current_run_article_visible_when_replaying_past_as_of(tmp_path: Path):
    cache = ArticleCache(tmp_path / "agent-state" / "articles")
    article = cache.put(url=_URL, final_url=_URL, title="Keeper fit", text="x" * 500, run_id="agent-backfill")
    stamped = article.model_copy(update={"retrieved_at": "2026-06-15T12:00:00+00:00"})
    cache._path(_URL).write_text(stamped.model_dump_json(), encoding="utf-8")

    assert cache.get(_URL, as_of="2026-06-14") is None
    assert cache.get(_URL, as_of="2026-06-14", current_run_id="agent-backfill") is not None


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


async def test_cached_redirect_marks_requested_and_final_urls_fetched(tmp_path: Path):
    deps = _deps(tmp_path)
    _seed_redirect(deps.articles, age_hours=6)

    with deps.runtime.run_trace():
        result = await _web_fetch(WebFetchArgs(url=_URL), deps)

    assert result.ok and result.payload["url"] == _FINAL_URL
    requested = deps.source_memory.seen(_URL)
    final = deps.source_memory.seen(_FINAL_URL)
    assert requested.last_seen_run == deps.runtime.run_id and requested.disposition == "fetched"
    assert final.last_seen_run == deps.runtime.run_id and final.disposition == "fetched"
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
