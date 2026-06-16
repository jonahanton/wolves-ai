from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from wolves.agent.ledger import EvidenceLedger
from wolves.agent.source_memory import SourceMemory
from wolves.graph.artifacts import ArtifactRecord, RunArtifactStore
from wolves.graph.branch_coverage import BranchCoverage, branch_coverage
from wolves.graph.contracts import NodeOutcome, NodePatch, ResearchOutput
from wolves.observability.runtime import ObservedRuntime

if TYPE_CHECKING:
    from wolves.config import Settings

_INTERNAL_SOURCE_URLS = {"internal://get_odds", "internal://get_results_and_fixtures"}
_BASE_WORLDS = {"baseline", "model_base", "market_base"}


def _has_non_base_perturbation(worlds: dict) -> bool:
    """A non-base world that perturbs strengths: the material-day proxy."""
    return any(
        name not in _BASE_WORLDS and isinstance(spec, dict) and spec.get("perturbations")
        for name, spec in worlds.items()
    )


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
        run_context: dict[str, str] | None = None,
    ) -> None:
        self.artifacts = artifacts
        self.ledger = ledger
        self._runtime = runtime
        self._source_memory = source_memory
        self._run_context = run_context or {}
        self.nodes: list[NodeRecord] = []
        self.challenges: list[str] = []
        self.dropped: list[str] = []
        self.wave = 0
        self.coverage_nudges = 0
        self.premortem_nudges = 0
        self.last_wave_cost_micros = 0
        self._cost_at_wave_start = runtime.budget.cost_micros

    def merge(self, ops: list[NodePatch], outcomes: list[NodeOutcome], *, advance_wave: bool = True) -> None:
        """Fold one wave's outcomes in: node records, lineage, evidence to
        ledger, challenges."""
        by_id = {op.node_id: op for op in ops}
        for outcome in outcomes:
            self._runtime.emit(
                "node",
                outcome.node_id,
                f"{outcome.kind} {'ok' if outcome.ok else 'FAILED'}: {(outcome.error or '')[:120]}",
                requests=outcome.requests,
                artifact_ids=outcome.artifact_ids,
                flags=outcome.flags,
            )
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
                    appended = self._ledger_entries(artifact.id, artifact.payload)
                    if appended:
                        self._runtime.emit(
                            "ledger",
                            artifact.created_by,
                            f"{appended} ledger entr{'y' if appended == 1 else 'ies'} from {artifact.id}",
                        )
                elif artifact.kind == "critique":
                    self.challenges.extend(artifact.payload.get("challenges", []))
        if advance_wave:
            self.wave += 1
            self.last_wave_cost_micros = self._runtime.budget.cost_micros - self._cost_at_wave_start
        self._cost_at_wave_start = self._runtime.budget.cost_micros

    def set_context(self, key: str, value: str) -> None:
        self._run_context[key] = value

    def _fetched_this_run(self, url: str) -> bool:
        if url in _INTERNAL_SOURCE_URLS:
            # Internal tool citations are first-party data, not web claims;
            # there is no page to fetch.
            return True
        if self._source_memory is None:
            return True
        seen = self._source_memory.seen(url)
        return seen is not None and seen.last_seen_run == self._runtime.run_id and seen.disposition == "fetched"

    def _ledger_entries(self, artifact_id: str, payload: dict) -> int:
        output = ResearchOutput.model_validate(payload)
        existing = {(e.claim.strip().lower(), e.source_url): e.id for e in self.ledger.all()}
        index_to_ledger_id: dict[int, str] = {}
        appended = 0
        demoted = 0
        for index, item in enumerate(output.evidence, start=1):
            key = (item.claim.strip().lower(), item.source_url)
            if key in existing:
                index_to_ledger_id[index] = existing[key]
                continue
            status = item.status
            if status == "confirmed" and not self._fetched_this_run(item.source_url):
                # A confirmed claim must be backed by a page the run actually
                # read; a snippet-only citation is at best probable.
                status = "probable"
                item.status = "probable"
                demoted += 1
                self._runtime.emit(
                    "evidence_demoted",
                    "blackboard",
                    f"confirmed demoted to probable, page never fetched: {item.source_url[:80]}",
                )
            entry = self.ledger.append(
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
            existing[key] = entry.id
            index_to_ledger_id[index] = entry.id
            appended += 1
        resolved = _resolve_branch_sources(output, index_to_ledger_id)
        if demoted or resolved:
            # The artifact must agree with the ledger, or later readers cite
            # a confidence the run already withdrew.
            self.artifacts.amend_payload(artifact_id, output.model_dump(mode="json"))
        return appended

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
            "artifacts": [self._artifact_entry(a) for a in self.artifacts.all()],
            "ledger": [
                {"id": e.id, "status": e.status, "team_id": e.team_id, "claim": e.claim[:80]} for e in self.ledger.all()
            ],
            "open_challenges": self._open_challenges(),
        }
        if self._run_context:
            state["run_context"] = {k: v[:1000] for k, v in self._run_context.items() if v}
        coverage = self.branch_coverage()
        if coverage.has_signal:
            state["branch_coverage"] = coverage.model_dump(mode="json")
        if self.dropped:
            state["last_wave_admission_drops"] = self.dropped
        return json.dumps(state, ensure_ascii=False)

    def _open_challenges(self) -> list[str]:
        challenges = list(self.challenges)
        for record in self.artifacts.all():
            if record.kind != "critique":
                continue
            artifact = self.artifacts.get(record.id)
            if artifact is None:
                continue
            for challenge in artifact.payload.get("challenges", []):
                text = str(challenge)
                if text not in challenges:
                    challenges.append(text)
            brief = str(artifact.payload.get("suggested_master_brief") or "").strip()
            if brief and brief not in challenges:
                challenges.append(brief)
        return challenges

    def branch_coverage(self) -> BranchCoverage:
        active = {node.node_id for node in self.nodes if node.replaced_by is None}
        return branch_coverage(self.artifacts, self.ledger, active_node_ids=active or None)

    def planned_node_count(self) -> int:
        return sum(1 for node in self.nodes if node.node_id != "coverage-research")

    def branch_follow_up_reason(self, settings: Settings) -> str | None:
        budget, caps = self._runtime.budget, self._runtime.caps
        reserve = int(settings.graph_forecast_reserve_usd * 1_000_000)
        if caps.max_cost_micros and caps.max_cost_micros - budget.cost_micros <= reserve:
            return None
        coverage = self.branch_coverage()
        return coverage.reason if coverage.needs_follow_up else None

    def premortem_follow_up_reason(self, settings: Settings) -> str | None:
        """One-shot nudge to pre-mortem a material candidate mixture before forecast."""
        if not settings.graph_premortem_enabled or self.premortem_nudges:
            return None
        budget, caps = self._runtime.budget, self._runtime.caps
        reserve = int(settings.graph_forecast_reserve_usd * 1_000_000)
        if caps.max_cost_micros and caps.max_cost_micros - budget.cost_micros <= reserve:
            return None
        if any(record.kind == "critique" for record in self.artifacts.all()):
            return None
        if not self._has_premortem_candidate(material_only=settings.graph_premortem_on_escalation_only):
            return None
        return "pre-mortem the candidate mixture before publishing"

    def _has_premortem_candidate(self, *, material_only: bool) -> bool:
        for record in self.artifacts.all():
            if record.kind not in {"mixture", "forecast"}:
                continue
            if not material_only:
                return True
            artifact = self.artifacts.get(record.id)
            if artifact is None:
                continue
            worlds = artifact.payload.get("worlds")
            if isinstance(worlds, dict) and _has_non_base_perturbation(worlds):
                return True
        return False

    def _artifact_entry(self, record: ArtifactRecord) -> dict[str, object]:
        entry = {"id": record.id, "kind": record.kind, "summary": record.summary[:100], "by": record.created_by}
        if record.kind != "evidence":
            return entry
        artifact = self.artifacts.get(record.id)
        if artifact is None:
            return entry
        branches = artifact.payload.get("candidate_branches")
        if not isinstance(branches, list) or not branches:
            return entry
        keys = [
            str(branch.get("branch_id"))
            for branch in branches
            if isinstance(branch, dict) and branch.get("branch_id")
        ]
        if keys:
            entry["candidate_branches"] = keys[:6]
        return entry


def _resolve_branch_sources(output: ResearchOutput, index_to_ledger_id: dict[int, str]) -> bool:
    changed = False
    for branch in output.candidate_branches:
        resolved = [index_to_ledger_id[index] for index in branch.evidence_indices if index in index_to_ledger_id]
        if not resolved:
            continue
        merged = list(dict.fromkeys([*branch.source_ids, *resolved]))
        if merged == branch.source_ids:
            continue
        branch.source_ids = merged
        changed = True
    return changed
