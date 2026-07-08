from __future__ import annotations

from wolves.llm.pricing import cost_micros


def test_cache_tokens_are_carved_out_of_the_inclusive_input_count():
    usage = {"input": 3_000_000, "output": 1_000_000, "cache_write": 1_000_000, "cache_read": 1_000_000}
    assert cost_micros("claude-sonnet-5", usage) == (3_000_000 + 15_000_000 + 3_750_000 + 300_000)


def test_fully_cached_input_bills_no_base_rate_tokens():
    usage = {"input": 2_000_000, "output": 0, "cache_write": 1_000_000, "cache_read": 1_000_000}
    assert cost_micros("claude-sonnet-5", usage) == (3_750_000 + 300_000)


def test_dated_model_id_normalised_to_price_key():
    usage = {"input": 1_000_000, "output": 0}
    assert cost_micros("claude-haiku-4-5-20251001", usage) == 1_000_000


def test_unknown_model_falls_back_to_sonnet_rates():
    usage = {"input": 1_000_000, "output": 0}
    assert cost_micros("mystery-model", usage) == 3_000_000


def test_fractional_micros_round_up():
    assert cost_micros("claude-haiku-4-5", {"input": 1, "output": 0}) == 1
