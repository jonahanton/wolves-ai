"""The quant workbench namespace, preloaded as ``wq`` in the sandbox."""

from wolves.quant.wolves_quant._data import (
    artifact,
    artifact_path,
    artifacts,
    fixtures,
    load_calibration,
    load_ledger,
    load_market_series,
    load_matches,
    load_ratings,
    query,
    teams,
)
from wolves.quant.wolves_quant._insights import (
    market_gaps,
    market_movement,
    model_explain,
    path_difficulty,
    path_tree,
)
from wolves.quant.wolves_quant._mixture import Factor, Scenario, scenario_mixture
from wolves.quant.wolves_quant._sanitise import sanitise as _sanitise
from wolves.quant.wolves_quant._sim import (
    baseline,
    impact,
    implied_delta,
    match_probs,
    noise_floor,
    posterior_draws,
    reach,
    score_grid,
    simulate,
    title_uncertainty,
    update_from_result,
)
from wolves.quant.wolves_quant._spread import mixture_spread
from wolves.quant.wolves_quant._state import finalise as _finalise
from wolves.sim.perturbations import PERTURBATIONS, DeltaDistribution

# The perturbation constructors are exported straight off the registry, so a
# new type reaches the wq namespace with one PERTURBATIONS entry and no edit here.
_PERTURBATION_EXPORTS = {spec.model.__name__: spec.model for spec in PERTURBATIONS}
globals().update(_PERTURBATION_EXPORTS)

__all__ = [
    "DeltaDistribution",
    "Factor",
    "Scenario",
    *sorted(_PERTURBATION_EXPORTS),
    "artifact",
    "artifact_path",
    "artifacts",
    "baseline",
    "fixtures",
    "impact",
    "implied_delta",
    "load_calibration",
    "load_ledger",
    "load_market_series",
    "load_matches",
    "load_ratings",
    "market_gaps",
    "market_movement",
    "match_probs",
    "mixture_spread",
    "model_explain",
    "noise_floor",
    "path_difficulty",
    "path_tree",
    "posterior_draws",
    "query",
    "reach",
    "scenario_mixture",
    "score_grid",
    "simulate",
    "teams",
    "title_uncertainty",
    "update_from_result",
]
