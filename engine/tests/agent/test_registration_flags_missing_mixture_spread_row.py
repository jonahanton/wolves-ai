from __future__ import annotations

from wolves.agent.audit_policy import intrinsic_missing_rows


def _mixture(weights: dict[str, float], *, audit_keys: list[str] | None = None) -> dict:
    payload: dict = {
        "mixture": {"france": 0.2},
        "conditionals": {},
        "weights": weights,
        "worlds": {name: {} for name in weights},
    }
    if audit_keys is not None:
        payload["factor_audit"] = {
            "verdict": "checked",
            "checks": [{"key": key, "status": "checked", "summary": "x"} for key in audit_keys],
        }
    return payload


def test_large_non_base_without_spread_row_is_flagged():
    payload = _mixture({"model_base": 0.4, "market_base": 0.3, "france_partial": 0.3}, audit_keys=["bases"])
    assert intrinsic_missing_rows(payload) == ["mixture_spread"]


def test_large_non_base_with_spread_row_is_clean():
    payload = _mixture(
        {"model_base": 0.4, "market_base": 0.3, "france_partial": 0.3},
        audit_keys=["bases", "mixture_spread"],
    )
    assert intrinsic_missing_rows(payload) == []


def test_small_non_base_owes_nothing():
    payload = _mixture({"model_base": 0.95, "france_partial": 0.05}, audit_keys=None)
    assert intrinsic_missing_rows(payload) == []
