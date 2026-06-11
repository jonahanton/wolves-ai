from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.source_memory import SourceMemory
from wolves.agent.tools.retrieval.web_fetch import WebFetchArgs, _web_fetch


async def test_second_fetch_of_the_same_url_returns_a_notice(tmp_path: Path):
    memory = SourceMemory(tmp_path / "agent-state" / "sources_seen.jsonl")
    deps = dataclasses.replace(build_graph_deps(tmp_path), source_memory=memory)
    memory.record("https://www.espn.com/tracker", run_id=deps.runtime.run_id, disposition="fetched")
    memory.record("https://www.espn.com/yesterday", run_id="agent-yesterday", disposition="fetched")

    with deps.runtime.run_trace():
        repeat = await _web_fetch(WebFetchArgs(url="https://www.espn.com/tracker"), deps)
        fresh = await _web_fetch(WebFetchArgs(url="https://www.espn.com/yesterday"), deps)

    assert repeat.ok and repeat.payload is not None
    assert "already fetched this run" in repeat.payload["notice"]
    # A previous run's fetch is not a reason to skip today's read.
    assert fresh.payload is not None and "notice" not in fresh.payload
    deps.runtime.shutdown()
