"""The single source of truth for which factor_audit coverage rows a mixture
must carry. Shared by the submit validator and the registration-time guard so
the two can never disagree about what a large mixture owes; that disagreement
is what let a structurally invalid artifact reach submission undetected."""

from __future__ import annotations

BASE_WORLDS = frozenset({"baseline", "model_base", "market_base"})
LARGE_NON_BASE_WEIGHT = 0.15

VALID_AUDIT_STATUSES = frozenset({"checked", "not_material", "not_applicable", "missing"})


def non_base_mass(weights: dict[str, float]) -> float:
    return sum(weight for name, weight in weights.items() if name not in BASE_WORLDS)


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
    weights: dict[str, float] = payload.get("weights") or {}
    if not weights or not payload.get("worlds"):
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
