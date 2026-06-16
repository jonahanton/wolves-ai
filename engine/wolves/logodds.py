"""Log-odds helpers shared by the publish-time blend and the quant workbench."""

from __future__ import annotations

import math


def to_log_odds(p: float) -> float:
    clamped = min(max(p, 1e-9), 1.0 - 1e-9)
    return math.log(clamped / (1.0 - clamped))


def from_log_odds(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))
