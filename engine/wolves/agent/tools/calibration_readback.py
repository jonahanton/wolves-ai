from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.calibration import CalibrationLedger, governor_scale
from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class CalibrationReadbackArgs(BaseModel):
    window: int = 20


async def _calibration_readback(args: CalibrationReadbackArgs, deps: AgentDeps) -> ToolResult[Any]:
    scores = CalibrationLedger(deps.settings.calibration_path).scores()
    recent = scores[-args.window :]

    def mean(metric: str, name: str) -> float | None:
        values = [getattr(s, metric)[name] for s in recent if name in getattr(s, metric)]
        return round(sum(values) / len(values), 4) if values else None

    pnls = [s.adjustment_pnl for s in recent if s.adjustment_pnl is not None]
    return ToolResult(
        payload={
            "scored_matches": len(scores),
            "window": len(recent),
            "mean_log_loss": {n: mean("log_loss", n) for n in ("model", "market", "frozen_sim", "uniform")},
            "mean_brier": {n: mean("brier", n) for n in ("model", "market", "frozen_sim", "uniform")},
            "adjustment_pnl": round(sum(pnls), 4) if pnls else None,
            "adjusted_matches": len(pnls),
            "governor_scale": governor_scale(scores, window=args.window),
        }
    )


SPEC = ToolSpec(
    name="calibration_readback",
    description=(
        "Your own track record: trailing proper scores against the market and the frozen "
        "no-agent baseline, adjustment PnL (log-loss saved by your moves) and the trust "
        "governor's current scale. Free to call; read it before big moves."
    ),
    args_model=CalibrationReadbackArgs,
    fn=_calibration_readback,
)
