from __future__ import annotations

from pathlib import Path

from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb
from wolves.observability import Caps, EventLog, InMemoryTracer, ObservedRuntime, build_runtime


def _runtime(tmp_path: Path) -> ObservedRuntime:
    return build_runtime(run_id="test-run", tracer=InMemoryTracer(), caps=Caps.small(), runs_root=tmp_path)


async def test_observed_web_search_and_fetch(tmp_path: Path):
    runtime = _runtime(tmp_path)
    web = ObservedWeb(runtime=runtime, brave=FakeSearchClient(provider="brave"), fetch=FakeFetchClient())

    with runtime.observe(kind="node", actor="research-1"):
        result = await web.search(actor="research-1", query="world cup final odds")
        page = await web.fetch(actor="research-1", url=result.hits[0].url)
    runtime.shutdown()

    assert result.provider == "brave" and result.hits
    assert page.text and page.content_hash.startswith("sha256:")

    events = EventLog.read(runtime.paths.events)
    assert any(e.kind == "web_search" for e in events)
    assert any(e.kind == "fetch" for e in events)
    assert runtime.budget.search_calls == 1 and runtime.budget.fetch_calls == 1


async def test_provider_selection_uses_exa_for_semantic_and_brave_for_fresh(tmp_path: Path):
    runtime = _runtime(tmp_path)
    brave = FakeSearchClient(provider="brave")
    exa = FakeSearchClient(provider="exa")
    web = ObservedWeb(runtime=runtime, brave=brave, exa=exa)

    with runtime.observe(kind="node", actor="r"):
        default = await web.search(actor="r", query="q")
        fresh = await web.search(actor="r", query="q", freshness="pd")
        explicit = await web.search(actor="r", query="q", provider="exa")
    runtime.shutdown()

    assert default.provider == "exa"
    assert fresh.provider == "brave"
    assert explicit.provider == "exa"
