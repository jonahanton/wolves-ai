from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from wolves.agent.calibration import CalibrationLedger
from wolves.agent.consensus import longshot_shade, publish_scale
from wolves.agent.forecast_artifact import (
    ForecastArtifactError,
    PublishedWorld,
    govern_outputs,
    mixed_outputs,
    simulate_worlds,
    worlds_from_payload,
)
from wolves.sim.api import SimOutputs
from wolves.sim.mc import SimResult
from wolves.sim.results_store import persisted_results

if TYPE_CHECKING:
    from wolves.agent.deps import AgentDeps


@dataclass(frozen=True)
class PublishSurface:
    artifact_id: str
    worlds: list[PublishedWorld]
    n_sims: int
    seed: int
    outputs: SimOutputs
    per_world_results: dict[str, SimResult]
    raw_titles: dict[str, float]
    published_titles: dict[str, float]
    baseline_titles: dict[str, float]
    anchor_result: SimResult | None
    governor_scale: float
    effective_d: float

    @property
    def governor_active(self) -> bool:
        return self.effective_d != 1.0


def _extremising_title_anchor(deps: AgentDeps, baseline_titles: dict[str, float]) -> dict[str, float] | None:
    """The title anchor extremising pushes away from; None keeps the sim baseline."""
    from wolves.agent.consensus import blend_log_odds
    from wolves.agent.tools.submission._validation import _anchors

    choice = deps.settings.extremising_anchor
    if choice == "baseline":
        return None
    market = _anchors(deps).market_titles
    if not market:
        return None
    if choice == "market":
        return longshot_shade(market, alpha=deps.settings.longshot_shade_alpha)
    return blend_log_odds(market, baseline_titles, d=0.5, renormalise=True)


def publish_surface(
    deps: AgentDeps, artifact_id: str, *, n_sims: int | None = None, seed: int | None = None
) -> PublishSurface | None:
    """Replay the exact title surface a submitted artifact will publish."""
    if deps.forecaster is None or deps.artifacts is None:
        return None
    n = max(n_sims or deps.publish_requested_n_sims or deps.settings.n_sims, deps.settings.publish_n_sims)
    s = deps.publish_seed if seed is None else seed
    key = (artifact_id, n, s)
    if key in deps.submission.publish_surface_by_artifact:
        return deps.submission.publish_surface_by_artifact[key]
    artifact = deps.artifacts.get(artifact_id)
    if artifact is None:
        return None

    try:
        worlds = worlds_from_payload(artifact.payload)
    except ForecastArtifactError:
        return None
    played = persisted_results(deps.settings)
    per_world_results = simulate_worlds(deps.forecaster, worlds, n_sims=n, seed=s, extra_results=played)
    outputs = mixed_outputs(
        deps.forecaster,
        worlds,
        n_sims=n,
        seed=s,
        extra_results=played,
        per_world_results=per_world_results,
    )
    raw_titles = {team.team_id: team.champion_prob for team in outputs.teams}
    governor_scale = CalibrationLedger(deps.settings.calibration_path).scale(window=deps.settings.governor_window)
    effective_d = publish_scale(
        extremising_d=deps.settings.extremising_d,
        governor_scale=governor_scale,
        shrink_weight=deps.settings.governor_shrink_weight,
    )
    anchor_result = None
    baseline_titles: dict[str, float] = {}
    anchor: SimOutputs | None = None
    if effective_d != 1.0 or (deps.settings.dispersion_floor_enabled and len(worlds) > 1):
        anchor_result = deps.forecaster.simulate(
            n_sims=n,
            seed=s,
            results=deps.forecaster.played_results(extra_results=played),
        )
        anchor = deps.forecaster.sim_outputs(n_sims=n, seed=s, extra_results=played, result=anchor_result)
        baseline_titles = {team.team_id: team.champion_prob for team in anchor.teams}
    if effective_d != 1.0 and anchor is not None:
        title_anchor = _extremising_title_anchor(deps, baseline_titles)
        govern_outputs(outputs, anchor, d=effective_d, title_anchor=title_anchor)
    if deps.settings.longshot_shade_alpha and deps.settings.extremising_anchor != "market":
        shaded = longshot_shade(
            {team.team_id: team.champion_prob for team in outputs.teams},
            alpha=deps.settings.longshot_shade_alpha,
        )
        for team in outputs.teams:
            team.champion_prob = round(shaded[team.team_id], 6)
    surface = PublishSurface(
        artifact_id=artifact_id,
        worlds=worlds,
        n_sims=n,
        seed=s,
        outputs=outputs,
        per_world_results=per_world_results,
        raw_titles=raw_titles,
        published_titles={team.team_id: team.champion_prob for team in outputs.teams},
        baseline_titles=baseline_titles,
        anchor_result=anchor_result,
        governor_scale=governor_scale,
        effective_d=effective_d,
    )
    deps.submission.publish_surface_by_artifact[key] = surface
    return surface
