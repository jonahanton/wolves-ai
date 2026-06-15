from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.contracts import LedgerStatus
from wolves.graph.artifacts import MissingRunIndexError, RunArtifactStore
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import run_dir
from wolves.snapshot import Snapshot

_SUMMARY_LIMIT = 180
_JOURNAL_LIMIT = 1800


class EventDigest(BaseModel):
    events: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    web_searches: int = 0
    fetches: int = 0
    quant_execs: int = 0
    waves: int = 0
    node_failures: list[str] = Field(default_factory=list)
    validation_failures: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    accepted: bool = False


class ArtifactDigest(BaseModel):
    counts: dict[str, int] = Field(default_factory=dict)
    accepted_artifact_id: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    quant_findings: list[str] = Field(default_factory=list)
    workspace_artifacts: list[str] = Field(default_factory=list)


class SourceDigest(BaseModel):
    ledger_counts: dict[LedgerStatus, int] = Field(default_factory=dict)
    ranked_sources: list[dict[str, Any]] = Field(default_factory=list)
    cited_sources: list[dict[str, Any]] = Field(default_factory=list)


class PreviousRunDigest(BaseModel):
    run_id: str
    created_at: str
    artifact_index_available: bool = False
    events_available: bool = False
    journal_available: bool = False
    events: EventDigest = Field(default_factory=EventDigest)
    artifacts: ArtifactDigest = Field(default_factory=ArtifactDigest)
    sources: SourceDigest = Field(default_factory=SourceDigest)
    journal_tail: str = ""
    warnings: list[str] = Field(default_factory=list)

    def master_summary(self) -> str:
        parts = [f"{self.run_id}: {self.events.waves} wave(s), {self.events.web_searches} search(es)"]
        if self.events.quant_execs:
            parts.append(f"{self.events.quant_execs} quant script(s)")
        if self.artifacts.accepted_artifact_id:
            parts.append(f"accepted {self.artifacts.accepted_artifact_id}")
        if self.artifacts.quant_findings:
            parts.append("quant: " + " ".join(self.artifacts.quant_findings[:2]))
        if self.events.validation_failures:
            parts.append("validator repairs: " + "; ".join(self.events.validation_failures[:2]))
        if self.events.node_failures:
            parts.append("failed nodes: " + "; ".join(self.events.node_failures[:2]))
        if self.sources.ranked_sources:
            best = self.sources.ranked_sources[0]
            parts.append(f"top ranked source: {best.get('title') or best.get('url')}")
        parts.append("Use this as an audit trail, not a template to inherit.")
        return " ".join(part for part in parts if part)


def build_previous_run_digest(
    snapshot: Snapshot,
    *,
    settings,
    store: RunArtifactStore | None = None,
) -> PreviousRunDigest:
    digest = PreviousRunDigest(run_id=snapshot.run.run_id, created_at=snapshot.run.created_at)
    run_path = run_dir(settings.runs_root, snapshot.run.run_id)
    digest.events = _event_digest(run_path / "events.jsonl")
    digest.events_available = (run_path / "events.jsonl").exists()
    digest.journal_tail = _journal_tail(run_path / "journal.md")
    digest.journal_available = bool(digest.journal_tail)
    if store is None:
        try:
            store = RunArtifactStore.open_run(ArtifactStore(settings), snapshot.run.run_id)
        except MissingRunIndexError:
            digest.warnings.append(f"artifact index missing for {snapshot.run.run_id}")
    if store is not None:
        digest.artifact_index_available = True
        digest.artifacts = _artifact_digest(snapshot, store)
    digest.sources = _source_digest(snapshot, store)
    if not digest.events_available:
        digest.warnings.append(f"events missing for {snapshot.run.run_id}")
    if not digest.journal_available:
        digest.warnings.append(f"journal missing for {snapshot.run.run_id}")
    return digest


def _event_digest(path: Path) -> EventDigest:
    digest = EventDigest()
    if not path.exists():
        return digest
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        digest.events += 1
        kind = event.get("kind")
        summary = str(event.get("summary") or "")
        if kind == "llm_call":
            digest.llm_calls += 1
        elif kind == "tool_call":
            digest.tool_calls += 1
        elif kind == "web_search":
            digest.web_searches += 1
        elif kind == "fetch":
            digest.fetches += 1
        elif kind == "quant_exec":
            digest.quant_execs += 1
        elif kind == "graph_patch":
            digest.waves += 1
        elif kind == "node" and "FAILED" in summary:
            digest.node_failures.append(summary[:_SUMMARY_LIMIT])
        elif kind == "validation":
            if "accepted" in summary:
                digest.accepted = True
            elif "rejected" in summary:
                digest.validation_failures.append(summary[:_SUMMARY_LIMIT])
        elif kind == "escalation":
            digest.escalations.append(summary[:_SUMMARY_LIMIT])
    return digest


def _artifact_digest(snapshot: Snapshot, store: RunArtifactStore) -> ArtifactDigest:
    records = store.all()
    counts = Counter(record.kind for record in records)
    digest = ArtifactDigest(
        counts=dict(sorted(counts.items())),
        accepted_artifact_id=snapshot.agent.artifact_id if snapshot.agent is not None else "",
    )
    for record in records:
        digest.artifacts.append(
            {
                "id": record.id,
                "kind": record.kind,
                "created_by": record.created_by,
                "summary": record.summary[:_SUMMARY_LIMIT],
                "has_workspace": record.workspace_prefix is not None,
            }
        )
        if record.workspace_prefix is not None:
            digest.workspace_artifacts.append(record.id)
        if record.kind != "quant":
            continue
        artifact = store.get(record.id)
        if artifact is None:
            continue
        summary = artifact.payload.get("summary") or record.summary
        digest.quant_findings.append(str(summary)[:_SUMMARY_LIMIT])
    return digest


def _source_digest(snapshot: Snapshot, store: RunArtifactStore | None) -> SourceDigest:
    digest = SourceDigest()
    if snapshot.agent is not None:
        counts = Counter(entry.status for entry in snapshot.agent.ledger_entries)
        digest.ledger_counts = dict(sorted(counts.items()))
        cited = sorted(snapshot.agent.ledger_entries, key=lambda e: (-(e.relevance or 0.0), e.created_at))
        digest.cited_sources = [
            {
                "url": entry.source_url,
                "title": entry.title or "",
                "team_id": entry.team_id,
                "status": entry.status,
                "claim": entry.claim[:_SUMMARY_LIMIT],
            }
            for entry in cited[:8]
        ]
    if store is None:
        return digest
    ranked: list[dict[str, Any]] = []
    for record in store.all():
        if record.kind != "retrieval":
            continue
        artifact = store.get(record.id)
        if artifact is None:
            continue
        for row in artifact.payload.get("rankings") or []:
            ranked.append(
                {
                    "retrieval_id": record.id,
                    "url": row.get("url"),
                    "title": row.get("title") or "",
                    "score": row.get("score"),
                    "reason": str(row.get("reason") or "")[:_SUMMARY_LIMIT],
                    "sub_question": str(artifact.payload.get("sub_question") or "")[:_SUMMARY_LIMIT],
                }
            )
    ranked.sort(key=lambda row: row["score"] if isinstance(row.get("score"), (int, float)) else -1, reverse=True)
    digest.ranked_sources = ranked[:8]
    return digest


def _journal_tail(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    return text[-_JOURNAL_LIMIT:]
