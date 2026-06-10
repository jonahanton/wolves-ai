from __future__ import annotations

from datetime import datetime

from wolves.markets.devig import consensus_probabilities, power_devig

from .contracts import OddsEvent


def market_last_updates(event: OddsEvent, *, market_key: str) -> list[datetime]:
    """Per-bookmaker re-price times for one market across the event's books."""
    return [
        market.last_update
        for bookmaker in event.bookmakers
        for market in bookmaker.markets
        if market.key == market_key and market.last_update is not None
    ]


def event_consensus(event: OddsEvent, *, market_key: str) -> dict[str, float]:
    """De-vig each bookmaker's market then average across books in log-odds."""
    per_book: list[dict[str, float]] = []
    for bookmaker in event.bookmakers:
        for market in bookmaker.markets:
            if market.key != market_key or not market.outcomes:
                continue
            probs = power_devig([o.price for o in market.outcomes])
            per_book.append({o.name: p for o, p in zip(market.outcomes, probs, strict=True)})
    return consensus_probabilities(per_book)
