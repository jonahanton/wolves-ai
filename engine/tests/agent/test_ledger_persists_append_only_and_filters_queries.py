from __future__ import annotations

from datetime import date
from pathlib import Path

from wolves.agent.ledger import EvidenceLedger


def test_entries_survive_reload_with_monotonic_ids(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    first = EvidenceLedger(path)
    first.append(claim="a", source_url="https://a", status="confirmed", mechanism="m", team_id="england")
    first.append(claim="b", source_url="https://b", status="rumour", mechanism="m", team_id="spain")

    reloaded = EvidenceLedger(path)
    assert [e.id for e in reloaded.all()] == ["led-0001", "led-0002"]
    third = reloaded.append(claim="c", source_url="https://c", status="probable", mechanism="m", team_id="england")
    assert third.id == "led-0003"


def test_query_filters_by_team_status_and_freshness(tmp_path: Path):
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="fresh",
        source_url="https://a",
        status="confirmed",
        mechanism="m",
        team_id="england",
        expiry="2026-06-20",
    )
    ledger.append(
        claim="stale",
        source_url="https://b",
        status="confirmed",
        mechanism="m",
        team_id="england",
        expiry="2026-06-01",
    )
    ledger.append(claim="other", source_url="https://c", status="rumour", mechanism="m", team_id="spain")

    assert {e.claim for e in ledger.query(team_id="england")} == {"fresh", "stale"}
    assert {e.claim for e in ledger.query(status="rumour")} == {"other"}
    fresh = ledger.query(team_id="england", fresh_on=date(2026, 6, 10))
    assert [e.claim for e in fresh] == ["fresh"]


def test_query_freshness_accepts_timestamp_expiries(tmp_path: Path):
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="kickoff-linked",
        source_url="https://a",
        status="confirmed",
        mechanism="m",
        expiry="2026-06-17T21:00:00Z",
    )

    fresh = ledger.query(fresh_on=date(2026, 6, 17))
    assert [e.claim for e in fresh] == ["kickoff-linked"]
