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


def test_seen_can_be_bounded_to_run_date(tmp_path):
    path = tmp_path / "sources_seen.jsonl"
    memory = SourceMemory(path)
    url = "https://www.reuters.com/sports/soccer/story"
    old = memory.record(url, run_id="agent-old", disposition="fetched").model_copy(
        update={"last_seen_at": "2026-06-13T12:00:00+00:00"}
    )
    new = memory.record(url, run_id="agent-new", disposition="ranked").model_copy(
        update={"last_seen_at": "2026-06-15T12:00:00+00:00"}
    )
    path.write_text(old.model_dump_json() + "\n" + new.model_dump_json() + "\n", encoding="utf-8")

    reloaded = SourceMemory(path)

    assert reloaded.seen(url, as_of="2026-06-14").last_seen_run == "agent-old"
    assert reloaded.seen(url, as_of="2026-06-15").last_seen_run == "agent-new"


def test_seen_keeps_current_run_visible_when_replaying_past_as_of(tmp_path):
    path = tmp_path / "sources_seen.jsonl"
    memory = SourceMemory(path)
    url = "https://www.reuters.com/sports/soccer/story"
    current = memory.record(url, run_id="agent-backfill", disposition="fetched").model_copy(
        update={"last_seen_at": "2026-06-15T12:00:00+00:00"}
    )
    path.write_text(current.model_dump_json() + "\n", encoding="utf-8")

    reloaded = SourceMemory(path)

    assert reloaded.seen(url, as_of="2026-06-14") is None
    assert reloaded.seen(url, as_of="2026-06-14", current_run_id="agent-backfill").last_seen_run == "agent-backfill"
