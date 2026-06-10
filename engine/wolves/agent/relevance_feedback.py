"""Score-vs-citation feedback for the relevance ranker. Every ranked candidate
either earned a ledger citation this run or did not; accumulated across runs
this is the evidence that promotes or demotes source tiers, replacing vibes."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from wolves.agent.ledger import EvidenceLedger
from wolves.graph.artifacts import RunArtifactStore


class RelevanceFeedback(BaseModel):
    run_id: str
    url: str
    tier: int | None
    score: float
    cited: bool


def relevance_feedback(artifacts: RunArtifactStore, ledger: EvidenceLedger, *, run_id: str) -> list[RelevanceFeedback]:
    cited = {entry.source_url for entry in ledger.all()}
    records: list[RelevanceFeedback] = []
    for record in artifacts.all():
        if record.kind != "retrieval":
            continue
        artifact = artifacts.get(record.id)
        if artifact is None:
            continue
        for ranking in artifact.payload.get("rankings", []):
            if ranking.get("score") is None:
                continue
            records.append(
                RelevanceFeedback(
                    run_id=run_id,
                    url=ranking["url"],
                    tier=ranking.get("tier"),
                    score=ranking["score"],
                    cited=ranking["url"] in cited,
                )
            )
    return records


def append_feedback(path: Path, records: list[RelevanceFeedback]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.model_dump()) + "\n")
