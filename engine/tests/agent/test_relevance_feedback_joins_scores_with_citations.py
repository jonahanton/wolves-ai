import json
from pathlib import Path

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.relevance_feedback import append_feedback, relevance_feedback
from wolves.config import Settings
from wolves.graph.artifacts import RunArtifactStore
from wolves.s3.artifacts import ArtifactStore


def test_relevance_feedback_joins_scores_with_citations(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    store = RunArtifactStore(ArtifactStore(settings), run_id="agent-test")
    store.add(
        kind="retrieval",
        created_by="research",
        summary="ranked 2 candidates",
        payload={
            "sub_question": "keeper fitness",
            "rankings": [
                {"url": "https://reuters.com/cited", "tier": 1, "score": 0.9, "reason": "direct"},
                {"url": "https://90min.com/ignored", "tier": 3, "score": 0.2, "reason": "bait"},
                {"url": "https://example.com/unscored", "tier": None, "score": None, "reason": "(not scored)"},
            ],
        },
    )
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append(
        claim="keeper fit",
        source_url="https://reuters.com/cited",
        status="confirmed",
        mechanism="keeper returns",
    )

    records = relevance_feedback(store, ledger, run_id="agent-test")
    by_url = {r.url: r for r in records}
    assert set(by_url) == {"https://reuters.com/cited", "https://90min.com/ignored"}
    assert by_url["https://reuters.com/cited"].cited is True
    assert by_url["https://90min.com/ignored"].cited is False

    path = tmp_path / "relevance_feedback.jsonl"
    append_feedback(path, records)
    append_feedback(path, [])
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(lines) == 2 and lines[0]["run_id"] == "agent-test"
