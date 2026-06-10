from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.insights.market import market_movement
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class MarketMovementArgs(BaseModel):
    history_points: int = 5


async def _market_movement(args: MarketMovementArgs, deps: AgentDeps) -> ToolResult[Any]:
    fc = deps.forecaster
    fmt = fc.fmt if fc is not None else None
    if fmt is None:
        from wolves.sim.format import load_format

        fmt = load_format(deps.settings.data_dir)
    movement = market_movement(deps.settings.runs_root / "odds-archive", fmt, history_points=args.history_points)
    payload = movement.model_dump(mode="json")
    payload["noise_floor_pp"] = deps.settings.market_movement_noise_floor_pp
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="market_movement",
    description=(
        "How the outright and match markets have moved across archived snapshots. The payload "
        "carries noise_floor_pp: bookmaker and Polymarket drifts below it are microstructure, "
        "not signal, so treat sub-floor moves as flat."
    ),
    args_model=MarketMovementArgs,
    fn=_market_movement,
)
