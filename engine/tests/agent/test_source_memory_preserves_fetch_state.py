from __future__ import annotations

from wolves.agent.source_memory import SourceMemory


def test_ranking_does_not_downgrade_same_run_fetch(tmp_path):
    memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    url = "https://www.reuters.com/sports/soccer/story"

    memory.record(url, run_id="agent-today", disposition="fetched")
    memory.record(url, run_id="agent-today", disposition="ranked")

    seen = memory.seen(url)
    assert seen is not None
    assert seen.last_seen_run == "agent-today"
    assert seen.disposition == "fetched"


def test_previous_fetch_does_not_make_todays_ranking_a_fetch(tmp_path):
    memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    url = "https://www.reuters.com/sports/soccer/story"

    memory.record(url, run_id="agent-yesterday", disposition="fetched")
    memory.record(url, run_id="agent-today", disposition="ranked")

    seen = memory.seen(url)
    assert seen is not None
    assert seen.first_seen_run == "agent-yesterday"
    assert seen.last_seen_run == "agent-today"
    assert seen.disposition == "ranked"


def test_ranking_does_not_clear_empty_page_memory(tmp_path):
    memory = SourceMemory(tmp_path / "sources_seen.jsonl")
    url = "https://www.fifa.com/empty"

    memory.record(url, run_id="agent-yesterday", disposition="empty")
    memory.record(url, run_id="agent-today", disposition="ranked")

    seen = memory.seen(url)
    assert seen is not None
    assert seen.last_seen_run == "agent-today"
    assert seen.disposition == "empty"
