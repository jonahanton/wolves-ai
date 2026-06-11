from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from wolves.forecast import Perturbation
from wolves.quant.wolves_quant._state import SESSION, SandboxContextError, context, forecaster

if TYPE_CHECKING:
    import pandas as pd


def _archive_dir() -> Path:
    ctx = context()
    if not ctx.archive_dir:
        raise SandboxContextError("odds archive", "market helpers need archived odds snapshots")
    return Path(ctx.archive_dir)


def market_gaps(*, n_sims: int | None = None, seed: int = 0) -> pd.DataFrame:
    """Model vs de-vigged market title probabilities with the published blend, largest gaps first."""
    import pandas as pd

    from wolves.insights.market_gaps import market_gaps as _gaps

    table = _gaps(forecaster(), _archive_dir(), n_sims=n_sims or context().default_n_sims, seed=seed)
    SESSION.usage.queries += 1
    return pd.DataFrame([g.model_dump() for g in table.gaps])


def market_movement(*, history_points: int = 4) -> pd.DataFrame:
    """Bookmaker outright movement across archived snapshots, one row per team."""
    import pandas as pd

    from wolves.insights.market import market_movement as _movement

    movement = _movement(_archive_dir(), forecaster().fmt, history_points=history_points)
    SESSION.usage.queries += 1
    return pd.DataFrame([m.model_dump() for m in movement.outright_bookmakers])


def model_explain(team: str) -> dict[str, Any]:
    """Why the model rates a team: weighted record, strongest match influences, Elo trajectory."""
    from wolves.insights.explain import model_explain as _explain

    SESSION.usage.queries += 1
    return _explain(forecaster(), team).model_dump(mode="json")


def path_tree(
    team: str,
    *,
    view: Literal["reach", "title"] = "reach",
    perturbations: tuple[Perturbation, ...] | list[Perturbation] = (),
    n_sims: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """One team's knockout route: qualification split, per-stage advance probabilities, likely opponents."""
    from wolves.insights.path_tree import team_path_tree

    SESSION.usage.sims += 1
    tree = team_path_tree(
        forecaster(),
        team,
        view=view,
        perturbations=tuple(perturbations),
        n_sims=n_sims or context().default_n_sims * 5,
        seed=seed,
    )
    return tree.model_dump(mode="json")
