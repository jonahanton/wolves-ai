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


# Anthropic published rates per 1M tokens. 5m cache writes are charged at
# 1.25x base input (the TTL the graph requests); cache reads at 10% of input.
ANTHROPIC_PRICES: dict[str, TokenPrices] = {
    "claude-opus-4-8": TokenPrices(input=5.00, output=25.00, cache_write=6.25, cache_read=0.50),
    "claude-sonnet-4-6": TokenPrices(input=3.00, output=15.00, cache_write=3.75, cache_read=0.30),
    "claude-haiku-4-5": TokenPrices(input=1.00, output=5.00, cache_write=1.25, cache_read=0.10),
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

    The ``input`` count follows genai-prices semantics and INCLUDES cached
    tokens, so the cache classes are subtracted before billing the uncached
    remainder at the base rate; billing all four independently double-counted
    every cached token and exhausted run budgets on paper."""
    prices = _prices(model)
    cache_write = int(usage.get("cache_write", 0))
    cache_read = int(usage.get("cache_read", 0))
    uncached_input = max(0, int(usage.get("input", 0)) - cache_write - cache_read)
    total = (
        uncached_input * prices.input
        + int(usage.get("output", 0)) * prices.output
        + cache_write * prices.cache_write
        + cache_read * prices.cache_read
    )
    return ceil(total)
