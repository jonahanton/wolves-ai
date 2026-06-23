from __future__ import annotations

from wolves.config import Settings
from wolves.observability.budget import Caps


def finalisation_reserves_micros(settings: Settings, caps: Caps) -> tuple[int, int]:
    forecast = int(settings.graph_forecast_reserve_usd * 1_000_000)
    referee = int(settings.graph_referee_reserve_usd * 1_000_000)
    if caps.max_cost_micros <= 0:
        return forecast, referee
    return _split_reserve(forecast, referee, caps.max_cost_micros // 2)


def finalisation_reserve_calls(settings: Settings, caps: Caps) -> tuple[int, int]:
    forecast = settings.graph_forecast_reserve_llm_calls
    referee = settings.graph_referee_reserve_llm_calls
    return _split_reserve(forecast, referee, caps.max_llm_calls // 2)


def _split_reserve(forecast: int, referee: int, budget: int) -> tuple[int, int]:
    """Honour the referee reserve first; it is the smaller, starvation-prone
    finalisation slot, so the forecast reserve absorbs any clamp shortfall."""
    total = min(forecast + referee, budget)
    effective_referee = min(referee, total)
    return total - effective_referee, effective_referee
