from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from wolves_backend.deps import Deps, get_deps
from wolves_backend.models import ResultsOut

router = APIRouter()

DepsDep = Annotated[Deps, Depends(get_deps)]


@router.get("/results")
async def results(deps: DepsDep) -> ResultsOut:
    return ResultsOut.model_validate({"results": await deps.engine.played_results()})
