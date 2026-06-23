from __future__ import annotations

from wolves.config import Settings
from wolves.observability.budget import Caps


def finalisation_reserves_micros(settings: Settings, caps: Caps) -> tuple[int, int]:
    forecast = int(settings.graph_forecast_reserve_usd * 1_000_000)
    referee = int(settings.graph_referee_reserve_usd * 1_000_000)
    if caps.max_cost_micros <= 0:
        return forecast, referee
    total = min(forecast + referee, caps.max_cost_micros // 2)
    effective_forecast = min(forecast, total)
    return effective_forecast, min(referee, total - effective_forecast)


def finalisation_reserve_calls(settings: Settings, caps: Caps) -> tuple[int, int]:
    forecast = settings.graph_forecast_reserve_llm_calls
    referee = settings.graph_referee_reserve_llm_calls
    total = min(forecast + referee, caps.max_llm_calls // 2)
    effective_forecast = min(forecast, total)
    return effective_forecast, min(referee, total - effective_forecast)
