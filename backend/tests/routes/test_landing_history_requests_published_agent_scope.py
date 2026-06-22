from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_landing_history_requests_published_agent_scope():
    runs_source = (REPO_ROOT / "web/src/lib/runs.ts").read_text(encoding="utf-8")
    page_source = (REPO_ROOT / "web/src/app/page.tsx").read_text(encoding="utf-8")

    assert "/teams/histories?ids=${ids}&scope=published-agent" in runs_source
    assert "loadPublishedAgentHistories(allIds)" in page_source
