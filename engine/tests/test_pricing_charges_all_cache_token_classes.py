from __future__ import annotations

from wolves.llm.client import harden_schema
from wolves.llm.pricing import cost_micros


def test_all_four_token_classes_billed_independently():
    usage = {"input": 1_000_000, "output": 1_000_000, "cache_write": 1_000_000, "cache_read": 1_000_000}
    assert cost_micros("claude-sonnet-4-6", usage) == (3_000_000 + 15_000_000 + 6_000_000 + 300_000)


def test_dated_model_id_normalised_to_price_key():
    usage = {"input": 1_000_000, "output": 0}
    assert cost_micros("claude-haiku-4-5-20251001", usage) == 1_000_000


def test_unknown_model_falls_back_to_sonnet_rates():
    usage = {"input": 1_000_000, "output": 0}
    assert cost_micros("mystery-model", usage) == 3_000_000


def test_fractional_micros_round_up():
    assert cost_micros("claude-haiku-4-5", {"input": 1, "output": 0}) == 1


def test_harden_schema_forbids_extras_and_requires_all_properties():
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "nested": {"type": "object", "properties": {"b": {"type": "integer"}}},
        },
    }
    hardened = harden_schema(schema)
    assert hardened["additionalProperties"] is False
    assert hardened["required"] == ["a", "nested"]
    nested = hardened["properties"]["nested"]
    assert nested["additionalProperties"] is False
    assert nested["required"] == ["b"]
