from __future__ import annotations

import json

from pydantic import BaseModel

from wolves.agent.ledger import EvidenceLedger
from wolves.graph.artifacts import ArtifactStore
from wolves.graph.contracts import Brief, NodeOutcome, ResearchOutput
from wolves.observability.runtime import ObservedRuntime


class NodeRecord(BaseModel):
    node_id: str
    kind: str
    objective: str
    ok: bool
    error: str | None = None


class Blackboard:
    """Single-writer run state: only the runner mutates it, between waves.

    Workers return values and never touch shared state; in particular the
    evidence ledger's len-based ids and append-mode writes are not
    concurrency-safe, so evidence reaches it only through ``merge``."""

    def __init__(self, *, artifacts: ArtifactStore, ledger: EvidenceLedger, runtime: ObservedRuntime) -> None:
        self.artifacts = artifacts
        self.ledger = ledger
        self._runtime = runtime
        self.nodes: list[NodeRecord] = []
        self.challenges: list[str] = []
        self.dropped: list[str] = []
        self.wave = 0

    def merge(self, briefs: list[Brief], outcomes: list[NodeOutcome]) -> None:
        """Fold one wave's outcomes in: node records, evidence to ledger, challenges."""
        objectives = {b.node_id: b.objective for b in briefs}
        for outcome in outcomes:
            self.nodes.append(
                NodeRecord(
                    node_id=outcome.node_id,
                    kind=outcome.kind,
                    objective=objectives.get(outcome.node_id, ""),
                    ok=outcome.ok,
                    error=outcome.error,
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

    def _ledger_entries(self, payload: dict) -> int:
        output = ResearchOutput.model_validate(payload)
        for item in output.evidence:
            self.ledger.append(
                claim=item.claim,
                source_url=item.source_url,
                status=item.status,
                mechanism=item.mechanism,
                proposed_delta=item.proposed_delta,
                expiry=item.expiry,
                team_id=item.team_id,
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
            },
            "nodes": [
                {
                    "node_id": n.node_id,
                    "kind": n.kind,
                    "objective": n.objective[:80],
                    "ok": n.ok,
                    **({"error": n.error[:120]} if n.error else {}),
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
