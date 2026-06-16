"""A pre-mortem tail lives on a critique artifact and carries no ledger source,
so without the analytical path branch_coverage would silently ignore it (B2).
It must surface as a serious, unaudited branch so the forecast nudge fires."""

from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_run_store
from wolves.agent.ledger import EvidenceLedger
from wolves.graph.branch_coverage import branch_coverage


def _tail(branch_id: str) -> dict:
    return {
        "branch_id": branch_id,
        "teams": ["france"],
        "hypothesis": "France is over-credited on reputation.",
        "support": "The structural move outruns the priced evidence.",
        "collapse_condition": "Collapse if the gap clears the noise floor.",
        "suggested_quant_question": "Re-price France against the longshot lens.",
    }


def test_premortem_tail_is_serious_and_unaudited(tmp_path: Path):
    store = build_run_store(tmp_path)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail("france-overcredit")]},
    )

    coverage = branch_coverage(store, ledger)

    assert "france-overcredit" in coverage.candidate_keys
    assert "france-overcredit" in coverage.serious_keys
    assert coverage.needs_follow_up is True


def test_priced_premortem_tail_clears_the_follow_up(tmp_path: Path):
    store = build_run_store(tmp_path)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail("france-overcredit")]},
    )
    store.add(
        kind="mixture",
        created_by="quant-2",
        summary="tail priced",
        payload={
            "weights": {"model_base": 0.8, "france-overcredit": 0.2},
            "branch_audit": {
                "verdict": "France tail priced.",
                "checks": [
                    {
                        "key": "france-overcredit",
                        "status": "priced",
                        "hypothesis": "France is over-credited.",
                        "summary": "Tail priced as its own world.",
                    }
                ],
            },
        },
    )

    coverage = branch_coverage(store, ledger)

    assert coverage.needs_follow_up is False
