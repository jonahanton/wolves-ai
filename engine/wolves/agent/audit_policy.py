"""The single source of truth for which factor_audit coverage rows a mixture
must carry. Shared by the submit validator and the registration-time guard so
the two can never disagree about what a large mixture owes; that disagreement
is what let a structurally invalid artifact reach submission undetected."""

from __future__ import annotations

BASE_WORLDS = frozenset({"baseline", "model_base", "market_base"})
LARGE_NON_BASE_WEIGHT = 0.15

VALID_AUDIT_STATUSES = frozenset({"checked", "not_material", "not_applicable", "missing"})

# Issues describing the cited artifact itself: only a quant node can clear them.
QUANT_OWNED_ISSUE_CODES = frozenset(
    {
        "branch_audit_self_inconsistent",
        "factor_audit_missing",
        "factor_audit_missing_coverage",
        "factor_audit_malformed",
        "market_audit_missing",
        "market_audit_missing_team",
        "prob_out_of_range",
        "partition_incoherent",
        "probs_incoherent",
        "artifact_unpublishable",
        "weight_dilution",
    }
)

KILLED_BRANCH_STATUSES = frozenset({"below_floor", "collapsed", "rejected"})
BASE_BRANCH_STATUSES = frozenset({"merged_into_base"})
BRANCH_SURVIVAL_MIN_WEIGHT = 1e-6


def repair_owner(code: str) -> str:
    return "quant" if code in QUANT_OWNED_ISSUE_CODES else "forecast"


def non_base_mass(weights: dict[str, float]) -> float:
    return sum(
        weight for name, weight in weights.items() if name not in BASE_WORLDS and isinstance(weight, int | float)
    )


def is_large_non_base(weights: dict[str, float]) -> bool:
    return non_base_mass(weights) >= LARGE_NON_BASE_WEIGHT


def required_keys(
    weights: dict[str, float],
    *,
    large_non_base: bool,
    has_market_stance: bool,
    has_previous_context: bool,
    has_priced_or_news: bool,
) -> set[str]:
    """The factor_audit check keys a submission must cover, given what it
    publishes. Quiet two-base days with no market stance owe nothing."""
    if not large_non_base and not has_market_stance:
        return set()
    required = {"mixture_spread"} if large_non_base else set()
    if has_previous_context:
        required.add("previous_continuity")
    if {"model_base", "market_base"} <= set(weights):
        required.add("bases")
    if has_market_stance:
        required.add("market_gap")
    if has_priced_or_news:
        required.add("ledger_pricing")
    return required


def audit_check_status(payload: dict) -> dict[str, str]:
    """Map of factor_audit check key to status, ignoring malformed rows."""
    audit = payload.get("factor_audit")
    checks = audit.get("checks") if isinstance(audit, dict) else None
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("key")): str(check.get("status"))
        for check in checks
        if isinstance(check, dict) and check.get("key")
    }


def intrinsic_missing_rows(payload: dict) -> list[str]:
    """Required rows derivable from the mixture payload alone, absent or marked
    missing. The submission-dependent obligations (market_gap, ledger_pricing,
    previous_continuity) are not knowable at registration time and are left to
    the submit validator."""
    weights = payload.get("weights")
    if not isinstance(weights, dict) or not payload.get("worlds"):
        return []
    required = required_keys(
        weights,
        large_non_base=is_large_non_base(weights),
        has_market_stance=False,
        has_previous_context=False,
        has_priced_or_news=False,
    )
    if not required:
        return []
    status = audit_check_status(payload)
    return sorted(key for key in required if status.get(key, "missing") == "missing")


def advisory_missing_rows(payload: dict) -> list[str]:
    """Rows a large-non-base mixture all but always owes at submit but the payload
    cannot prove, so the submit validator would only catch them once the run has
    no quant budget left to re-register. Surfaced at registration to warn, never
    to block."""
    weights = payload.get("weights")
    if not isinstance(weights, dict) or not payload.get("worlds") or not is_large_non_base(weights):
        return []
    if audit_check_status(payload).get("market_gap", "missing") in {"checked", "not_material"}:
        return []
    return ["market_gap"]


def branch_audit_contradictions(payload: dict) -> list[str]:
    audit = payload.get("branch_audit")
    checks = audit.get("checks") if isinstance(audit, dict) else None
    weights = payload.get("weights")
    if not isinstance(checks, list) or not isinstance(weights, dict):
        return []
    contradictions: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status") or "")
        world_names = check.get("world_names")
        if status not in KILLED_BRANCH_STATUSES | BASE_BRANCH_STATUSES or not isinstance(world_names, list):
            continue
        survivors = sorted(
            str(name)
            for name in world_names
            if str(name) not in BASE_WORLDS and weights.get(str(name), 0.0) > BRANCH_SURVIVAL_MIN_WEIGHT
        )
        if survivors:
            contradictions.append(f"{check.get('key')} ({status}) still weights {', '.join(survivors)}")
    return contradictions
