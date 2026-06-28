from __future__ import annotations

from pydantic import BaseModel, Field

from wolves.agent.ledger import EvidenceLedger
from wolves.graph.artifacts import RunArtifactStore

_PRICED = {"priced", "carried_forward"}
_COLLAPSED = {"collapsed", "below_floor", "rejected"}
_MERGED = {"merged_into_base"}
_AUDITED = _PRICED | _COLLAPSED | _MERGED | {"covered_by_child"}


class BranchCoverage(BaseModel):
    candidate_keys: list[str] = Field(default_factory=list)
    serious_keys: list[str] = Field(default_factory=list)
    audited_keys: list[str] = Field(default_factory=list)
    priced_keys: list[str] = Field(default_factory=list)
    collapsed_keys: list[str] = Field(default_factory=list)
    rejected_keys: list[str] = Field(default_factory=list)
    merged_keys: list[str] = Field(default_factory=list)
    missing_keys: list[str] = Field(default_factory=list)
    material_unaudited_keys: list[str] = Field(default_factory=list)
    all_survivors_merged_into_base: bool = False
    needs_follow_up: bool = False
    reason: str | None = None

    @property
    def has_signal(self) -> bool:
        return bool(self.candidate_keys or self.audited_keys)


def branch_coverage(
    store: RunArtifactStore,
    ledger: EvidenceLedger,
    *,
    active_node_ids: set[str] | None = None,
    max_critic_tails: int | None = None,
) -> BranchCoverage:
    candidates: dict[str, dict] = {}
    statuses: dict[str, str] = {}
    artifacts = []
    for record in store.all():
        if active_node_ids is not None and record.created_by not in active_node_ids:
            continue
        artifact = store.get(record.id)
        if artifact is None:
            continue
        artifacts.append(artifact)
        if artifact.kind == "evidence":
            _collect_candidates(candidates, artifact.payload, key="candidate_branches")
        elif artifact.kind == "critique":
            _collect_candidates(
                candidates, artifact.payload, key="tail_branches", analytical=True, limit=max_critic_tails
            )
    for artifact in artifacts:
        _collect_audit_statuses(statuses, artifact.payload, candidates)

    candidate_keys = sorted(candidates)
    serious = sorted(key for key, branch in candidates.items() if _serious_branch(branch, ledger))
    audited = sorted(key for key, status in statuses.items() if status in _AUDITED)
    priced = sorted(key for key, status in statuses.items() if status in _PRICED)
    collapsed = sorted(key for key, status in statuses.items() if status in _COLLAPSED)
    rejected = sorted(key for key, status in statuses.items() if status == "rejected")
    merged = sorted(key for key, status in statuses.items() if status in _MERGED)
    missing = sorted(set(serious) - set(audited))
    material_unaudited = missing
    needs_follow_up = bool(material_unaudited)
    reason = None
    if material_unaudited:
        reason = "serious candidate branches need quant adjudication: " + ", ".join(material_unaudited[:6])
    return BranchCoverage(
        candidate_keys=candidate_keys,
        serious_keys=serious,
        audited_keys=audited,
        priced_keys=priced,
        collapsed_keys=collapsed,
        rejected_keys=rejected,
        merged_keys=merged,
        missing_keys=missing,
        material_unaudited_keys=material_unaudited,
        all_survivors_merged_into_base=bool(serious and not missing and merged and not priced),
        needs_follow_up=needs_follow_up,
        reason=reason,
    )


_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def _confidence_rank(branch: dict) -> int:
    return _CONFIDENCE_RANK.get(str(branch.get("confidence") or "").lower(), 0)


def _collect_candidates(
    candidates: dict[str, dict], payload: dict, *, key: str, analytical: bool = False, limit: int | None = None
) -> None:
    branches = payload.get(key)
    if not isinstance(branches, list):
        return
    valid = [branch for branch in branches if isinstance(branch, dict) and branch.get("branch_id")]
    if limit is not None:
        # Capping keeps the most confident tails, so a low-confidence one never displaces a material one.
        valid = sorted(valid, key=_confidence_rank, reverse=True)[:limit]
    for branch in valid:
        branch_key = str(branch["branch_id"])
        # Analytical tails carry no ledger source but still earn adjudication.
        candidates.setdefault(branch_key, {**branch, "_analytical": True} if analytical else branch)


def _collect_audit_statuses(statuses: dict[str, str], payload: dict, candidates: dict[str, dict]) -> None:
    audit = payload.get("branch_audit")
    if not isinstance(audit, dict):
        return
    checks = audit.get("checks")
    if not isinstance(checks, list):
        return
    for check in checks:
        if not isinstance(check, dict) or not check.get("key"):
            continue
        status = str(check.get("status") or "")
        key = str(check["key"])
        statuses[key] = status
        candidate = candidates.get(key) or {}
        declared_parents = {str(parent) for parent in candidate.get("parent_branch_ids") or []}
        checked_parents = {str(parent) for parent in check.get("parent_branch_ids") or []}
        if status in _AUDITED:
            for parent in declared_parents & checked_parents & candidates.keys():
                statuses.setdefault(parent, "covered_by_child")


def _serious_branch(branch: dict, ledger: EvidenceLedger) -> bool:
    source_ids = {str(value) for value in branch.get("source_ids") or []}
    if not source_ids:
        # An analytical tail has no ledger tie but still needs adjudication.
        return bool(branch.get("_analytical"))
    material_ledger_ids = {
        entry.id for entry in ledger.all() if entry.status in {"confirmed", "probable"} and entry.proposed_delta
    }
    if source_ids & material_ledger_ids:
        return True
    credible_ledger_ids = {entry.id for entry in ledger.all() if entry.status in {"confirmed", "probable"}}
    return str(branch.get("confidence") or "").lower() in {"medium", "high"} and bool(source_ids & credible_ledger_ids)
