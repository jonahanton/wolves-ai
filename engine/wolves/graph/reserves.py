from __future__ import annotations

from wolves.config import Settings
from wolves.observability.budget import Caps


def finalisation_reserves_micros(settings: Settings, caps: Caps) -> tuple[int, int]:
    forecast = int(settings.graph_forecast_reserve_usd * 1_000_000)
    referee = int(settings.graph_referee_reserve_usd * 1_000_000)
    if caps.max_cost_micros <= 0:
        return forecast, referee
    total = min(forecast + referee, caps.max_cost_micros // 2)
    effective_referee = min(referee, total)
    return total - effective_referee, effective_referee
