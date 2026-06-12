from __future__ import annotations

from pathlib import Path

from wolves.agent.article_cache import ArticleCache
from wolves.agent.ledger import EvidenceLedger
from wolves.run_agent import _ledger_entries


def test_ledger_entries_carry_cached_article_titles(tmp_path: Path):
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(claim="keeper fit", source_url="https://news.example/keeper", status="confirmed", mechanism="m")
    ledger.append(claim="uncached rumour", source_url="https://news.example/rumour", status="rumour", mechanism="m")
    articles = ArticleCache(tmp_path / "articles")
    articles.put(
        url="https://news.example/keeper",
        final_url="https://news.example/keeper",
        title="Keeper passed fit for the opener",
        text="body",
        run_id="agent-test",
    )

    entries = _ledger_entries(ledger, articles)

    assert entries[0].title == "Keeper passed fit for the opener"
    assert entries[1].title is None
