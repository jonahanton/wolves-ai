from __future__ import annotations

import math


def valid_price(value: object) -> float | None:
    """Decimal odds price, or None for anything unusable. Suspended or corrupt
    markets surface as zero, negative or non-finite prices; letting one through
    silently corrupts every downstream likelihood."""
    try:
        price = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 1.0 else None
