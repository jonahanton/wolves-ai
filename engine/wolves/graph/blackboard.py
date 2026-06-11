from __future__ import annotations

import json

from pydantic import BaseModel, Field

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.source_memory import SourceMemory
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.contracts import NodeOutcome, NodePatch, ResearchOutput
from wolves.observability.runtime import ObservedRuntime


class NodeRecord(BaseModel):
    node_id: str
    kind: str
    objective: str
    ok: bool
    error: str | None = None
    requests: int = 0
    replaced_by: str | None = None
    flags: list[str] = Field(default_factory=list)


class Blackboard:
    """Single-writer run state: only the runner mutates it, between waves.

    Workers return values and never touch shared state; in particular the
    evidence ledger's len-based ids and append-mode writes are not
    concurrency-safe, so evidence reaches it only through ``merge``."""

    def __init__(
        self,
        *,
        artifacts: RunArtifactStore,
        ledger: EvidenceLedger,
        runtime: ObservedRuntime,
        source_memory: SourceMemory | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.ledger = ledger
        self._runtime = runtime
        self._source_memory = source_memory
        self.nodes: list[NodeRecord] = []
        self.challenges: list[str] = []
        self.dropped: list[str] = []
        self.wave = 0
        self.last_wave_cost_micros = 0
        self._cost_at_wave_start = runtime.budget.cost_micros

    def merge(self, ops: list[NodePatch], outcomes: list[NodeOutcome]) -> None:
        """Fold one wave's outcomes in: node records, lineage, evidence to
        ledger, challenges."""
        by_id = {op.node_id: op for op in ops}
        for outcome in outcomes:
            op = by_id.get(outcome.node_id)
            if op is not None and op.replaces is not None:
                for node in self.nodes:
                    if node.node_id == op.replaces:
                        node.replaced_by = outcome.node_id
            self.nodes.append(
                NodeRecord(
                    node_id=outcome.node_id,
                    kind=outcome.kind,
                    objective=op.objective if op is not None else "",
                    ok=outcome.ok,
                    error=outcome.error,
                    requests=outcome.requests,
                    flags=outcome.flags,
                )
            )
            for artifact_id in outcome.artifact_ids:
                artifact = self.artifacts.get(artifact_id)
                if artifact is None:
                    continue
                if artifact.kind == "evidence":
                    appended = self._ledger_entries(artifact.payload)
                    if appended:
                        self._runtime.emit(
                            "ledger",
                            artifact.created_by,
                            f"{appended} ledger entr{'y' if appended == 1 else 'ies'} from {artifact.id}",
                        )
                elif artifact.kind == "critique":
                    self.challenges.extend(artifact.payload.get("challenges", []))
        self.wave += 1
        self.last_wave_cost_micros = self._runtime.budget.cost_micros - self._cost_at_wave_start
        self._cost_at_wave_start = self._runtime.budget.cost_micros

    def _fetched_this_run(self, url: str) -> bool:
        if not url.startswith("http"):
            return True
        if self._source_memory is None:
            return True
        seen = self._source_memory.seen(url)
        return seen is not None and seen.last_seen_run == self._runtime.run_id and seen.disposition == "fetched"

    def _ledger_entries(self, payload: dict) -> int:
        output = ResearchOutput.model_validate(payload)
        for item in output.evidence:
            status = item.status
            if status == "confirmed" and not self._fetched_this_run(item.source_url):
                # A confirmed claim must be backed by a page the run actually
                # read; a snippet-only citation is at best probable.
                status = "probable"
                self._runtime.emit(
                    "evidence_demoted",
                    "blackboard",
                    f"confirmed demoted to probable, page never fetched: {item.source_url[:80]}",
                )
            self.ledger.append(
                claim=item.claim,
                source_url=item.source_url,
                status=status,
                mechanism=item.mechanism,
                proposed_delta=item.proposed_delta,
                expiry=item.expiry,
                team_id=item.team_id,
                relevance=item.relevance,
                retrieval_id=item.retrieval_id,
            )
        return len(output.evidence)

    def summary(self) -> str:
        """Compact JSON for the master: metadata only, never payloads."""
        budget = self._runtime.budget
        caps = self._runtime.caps
        state = {
            "wave": self.wave,
            "budget": {
                "llm_calls": f"{budget.llm_calls}/{caps.max_llm_calls}",
                "cost_usd": round(budget.cost_micros / 1e6, 4),
                "ceiling_usd": round(caps.max_cost_micros / 1e6, 4),
                "remaining_usd": round(max(0, caps.max_cost_micros - budget.cost_micros) / 1e6, 4),
                "last_wave_cost_usd": round(self.last_wave_cost_micros / 1e6, 4),
            },
            "nodes": [
                {
                    "node_id": n.node_id,
                    "kind": n.kind,
                    "objective": n.objective[:80],
                    "ok": n.ok,
                    "requests": n.requests,
                    **({"error": n.error[:120]} if n.error else {}),
                    **({"replaced_by": n.replaced_by} if n.replaced_by else {}),
                    **({"flags": n.flags} if n.flags else {}),
                }
                for n in self.nodes
            ],
            "artifacts": [
                {"id": a.id, "kind": a.kind, "summary": a.summary[:100], "by": a.created_by}
                for a in self.artifacts.all()
            ],
            "ledger": [
                {"id": e.id, "status": e.status, "team_id": e.team_id, "claim": e.claim[:80]} for e in self.ledger.all()
            ],
            "open_challenges": self.challenges,
        }
        if self.dropped:
            state["last_wave_admission_drops"] = self.dropped
        return json.dumps(state, ensure_ascii=False)
