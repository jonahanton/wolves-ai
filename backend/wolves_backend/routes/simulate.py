from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from wolves.forecast import UnknownMatchError
from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import MatchGrid, SimulateRequest, SimulateResponse
from wolves_backend.sim import MatchAlreadyPlayedError, MatchTeamsUnknownError, Pin

router = APIRouter()

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.post("/simulate")
async def simulate(body: SimulateRequest, deps: DepsDep) -> SimulateResponse:
    pins = [Pin(match=p.match, home_goals=p.home_goals, away_goals=p.away_goals) for p in body.pins]
    try:
        payload = await deps.engine.simulate_pins(pins, n_sims=body.n_sims, seed=body.seed)
    except MatchAlreadyPlayedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UnknownMatchError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SimulateResponse.model_validate(payload)


@router.get("/matches/{match}/grid")
async def match_grid(match: int, deps: DepsDep) -> MatchGrid:
    try:
        payload = await deps.engine.match_grid(match)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"match {match} is not a tournament fixture") from exc
    except MatchTeamsUnknownError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MatchGrid.model_validate(payload)
