"""A pre-mortem tail lives on a critique artifact and carries no ledger source,
so without the analytical path branch_coverage would silently ignore it. It must
surface as a serious, unaudited branch so the forecast nudge fires."""

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


def test_verified_child_audit_covers_parent_without_copying_its_disposition(tmp_path: Path):
    store = build_run_store(tmp_path)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    child = {**_tail("france-draw-tail"), "parent_branch_ids": ["france-overcredit"]}
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail("france-overcredit"), child]},
    )
    store.add(
        kind="mixture",
        created_by="quant-2",
        summary="child priced",
        payload={
            "branch_audit": {
                "verdict": "Refined tail priced.",
                "checks": [
                    {
                        "key": "france-draw-tail",
                        "status": "priced",
                        "parent_branch_ids": ["france-overcredit"],
                    }
                ],
            }
        },
    )

    coverage = branch_coverage(store, ledger)

    assert "france-overcredit" in coverage.audited_keys
    assert "france-overcredit" not in coverage.priced_keys
    assert coverage.needs_follow_up is False


def test_max_critic_tails_caps_how_many_one_premortem_can_open(tmp_path: Path):
    store = build_run_store(tmp_path)
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    store.add(
        kind="critique",
        created_by="critic-1",
        summary="pre-mortem",
        payload={"challenges": [], "tail_branches": [_tail(f"tail-{i}") for i in range(5)]},
    )

    coverage = branch_coverage(store, ledger, max_critic_tails=2)

    assert coverage.candidate_keys == ["tail-0", "tail-1"]
    assert len(coverage.serious_keys) == 2
