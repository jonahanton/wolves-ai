from __future__ import annotations

from wolves.agent.audit_policy import advisory_missing_rows


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


def test_large_non_base_without_market_gap_row_is_advised():
    payload = _mixture({"model_base": 0.4, "market_base": 0.3, "france_partial": 0.3}, audit_keys=["bases"])
    assert advisory_missing_rows(payload) == ["market_gap"]


def test_market_gap_marked_not_material_is_clean():
    payload = _mixture(
        {"model_base": 0.4, "market_base": 0.3, "france_partial": 0.3},
        audit_keys=["bases"],
    )
    payload["factor_audit"]["checks"].append({"key": "market_gap", "status": "not_material", "summary": "on market"})
    assert advisory_missing_rows(payload) == []


def test_small_non_base_owes_no_advisory():
    payload = _mixture({"model_base": 0.95, "france_partial": 0.05}, audit_keys=None)
    assert advisory_missing_rows(payload) == []
