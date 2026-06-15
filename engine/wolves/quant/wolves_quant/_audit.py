from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from wolves.forecast import StrengthPerturbation
from wolves.quant.wolves_quant._state import SESSION

if TYPE_CHECKING:
    from wolves.quant.wolves_quant._mixture import Scenario

AuditStatus = Literal["checked", "not_material", "not_applicable", "missing"]
BranchStatus = Literal["priced", "collapsed", "below_floor", "rejected", "carried_forward", "merged_into_base"]


class CoverageCheck(BaseModel):
    key: str = Field(min_length=1)
    status: AuditStatus
    summary: str = Field(min_length=1)
    teams: list[str] = Field(default_factory=list)
    ledger_ids: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


class FactorAudit(BaseModel):
    verdict: str = Field(min_length=1)
    checks: list[CoverageCheck]
    notes: list[str] = Field(default_factory=list)


class BranchCheck(BaseModel):
    key: str = Field(min_length=1)
    status: BranchStatus
    hypothesis: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    teams: list[str] = Field(default_factory=list)
    ledger_ids: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    world_names: list[str] = Field(default_factory=list)


class BranchAudit(BaseModel):
    verdict: str = Field(min_length=1)
    checks: list[BranchCheck]
    notes: list[str] = Field(default_factory=list)


def factor_audit(
    checks: list[CoverageCheck | dict[str, Any]],
    *,
    verdict: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    audit = FactorAudit(
        verdict=verdict,
        checks=[check if isinstance(check, CoverageCheck) else CoverageCheck.model_validate(check) for check in checks],
        notes=notes or [],
    )
    return audit.model_dump(mode="json")


def branch_audit(
    checks: list[BranchCheck | dict[str, Any]],
    *,
    verdict: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    audit = BranchAudit(
        verdict=verdict,
        checks=[check if isinstance(check, BranchCheck) else BranchCheck.model_validate(check) for check in checks],
        notes=notes or [],
    )
    return audit.model_dump(mode="json")


def market_base_world(
    deltas: dict[str, float],
    *,
    weight: float,
    name: str = "market_base",
    reason: str = "market-implied title prices",
) -> Scenario:
    from wolves.quant.wolves_quant._mixture import Scenario

    return Scenario(
        name=name,
        weight=weight,
        perturbations=[
            StrengthPerturbation(team=team, delta=delta, reason=reason)
            for team, delta in sorted(deltas.items())
            if delta
        ],
    )


def result_attribution(
    *,
    summary: str,
    bracket_pp: dict[str, float] | None = None,
    strength_update_pp: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "summary": summary,
        "bracket_pp": bracket_pp or {},
        "strength_update_pp": strength_update_pp or {},
    }


def audit_mixture(
    mixture: dict[str, Any],
    audit: dict[str, Any] | FactorAudit,
    *,
    branches: dict[str, Any] | BranchAudit | None = None,
) -> dict[str, Any]:
    payload = dict(mixture)
    payload["factor_audit"] = FactorAudit.model_validate(audit).model_dump(mode="json")
    if branches is not None:
        payload["branch_audit"] = BranchAudit.model_validate(branches).model_dump(mode="json")
    if artifact_file := payload.get("artifact_file"):
        path = Path(artifact_file)
        if not path.is_absolute():
            path = SESSION.root / path
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload
