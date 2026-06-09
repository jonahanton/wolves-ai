from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class TokenPrices:
    """Prices in dollars per million tokens (== micro-dollars per token)."""

    input: float
    output: float
    cache_write: float
    cache_read: float


# Anthropic published rates per 1M tokens. 1h cache writes are charged at
# ~2x base input; cache reads at ~10% of input.
ANTHROPIC_PRICES: dict[str, TokenPrices] = {
    "claude-opus-4-8": TokenPrices(input=5.00, output=25.00, cache_write=10.00, cache_read=0.50),
    "claude-sonnet-4-6": TokenPrices(input=3.00, output=15.00, cache_write=6.00, cache_read=0.30),
    "claude-haiku-4-5": TokenPrices(input=1.00, output=5.00, cache_write=2.00, cache_read=0.10),
}

_DEFAULT = ANTHROPIC_PRICES["claude-sonnet-4-6"]


def _normalise(model: str) -> str:
    """Map a dated model id (e.g. ``claude-sonnet-4-6-20251001``) to a price key.

    Longest key first, so matching stays order-independent if keys ever overlap."""
    for key in sorted(ANTHROPIC_PRICES, key=len, reverse=True):
        if key in model:
            return key
    return model


def _prices(model: str) -> TokenPrices:
    return ANTHROPIC_PRICES.get(_normalise(model), _DEFAULT)


def cost_micros(model: str, usage: dict[str, int]) -> int:
    """Estimate cost in micro-dollars from raw token usage.

    Anthropic's ``input_tokens`` excludes cache tokens, so the four token
    classes are billed independently and summed."""
    prices = _prices(model)
    total = (
        int(usage.get("input", 0)) * prices.input
        + int(usage.get("output", 0)) * prices.output
        + int(usage.get("cache_write", 0)) * prices.cache_write
        + int(usage.get("cache_read", 0)) * prices.cache_read
    )
    return ceil(total)
