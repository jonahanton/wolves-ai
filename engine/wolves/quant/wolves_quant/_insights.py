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
    """Model vs de-vigged market title probabilities with a reference blend, largest gaps first."""
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


def path_difficulty(
    teams: list[str] | None = None,
    *,
    n_sims: int | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """Draw luck quantified: expected opponent strength per knockout stage
    (weighted over likely opponents) and a play-probability-weighted
    difficulty index, one row per team. Divergence from the strength ranking
    is bracket asymmetry the market may not price."""
    import pandas as pd

    from wolves.insights.path_tree import team_path_tree

    fc = forecaster()
    strength = dict(zip(list(fc.state.teams), [float(x) for x in fc.state.strengths], strict=True))
    rows: dict[str, dict[str, float]] = {}
    for team in teams or sorted(strength, key=strength.get, reverse=True)[:12]:
        tree = team_path_tree(fc, team, n_sims=n_sims or context().default_n_sims * 3, seed=seed)
        SESSION.usage.sims += 1
        index = weight = 0.0
        per_stage: dict[str, float] = {}
        for stage in tree.stages:
            exp_s = mass = 0.0
            for slot in stage.slots:
                for opp in slot.opponents:
                    w = slot.p_slot * opp.p_opponent_given_slot
                    exp_s += w * strength.get(opp.team, 0.0)
                    mass += w
            if mass == 0:
                continue
            per_stage[stage.stage] = round(exp_s / mass, 3)
            index += stage.p_play * (exp_s / mass)
            weight += stage.p_play
        rows[team] = {"difficulty": round(index / max(weight, 1e-9), 3), **per_stage}
    return pd.DataFrame(rows).T.sort_values("difficulty", ascending=False)


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
