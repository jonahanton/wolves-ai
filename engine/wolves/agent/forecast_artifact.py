"""Resolve a submitted forecast artifact into publishable outputs.

The artifact carries world configurations (typed perturbations plus
weights); the harness re-simulates each world and mixes every published
probability by weight, so the snapshot is an integral over the agent's
latent model, never a typed number. Path-narrative blocks (focus-team paths,
slots, groups) come from the modal world: probabilities are linear in the
mixture, bracket narratives are not, and the modal world is the honest
single story to tell."""

from __future__ import annotations

from pydantic import BaseModel, Field

from wolves.forecast import Forecaster, Perturbation
from wolves.sim.api import SimOutputs
from wolves.sim.format import PlayedResult
from wolves.sim.latent import LatentEffect
from wolves.sim.mc import SimResult
from wolves.sim.perturbations import parse_perturbation, spec_for


class PublishedWorld(BaseModel):
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    perturbations: list[Perturbation] = Field(default_factory=list)
    latent_effects: list[LatentEffect] = Field(default_factory=list)


class ForecastArtifactError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def worlds_from_payload(payload: dict) -> list[PublishedWorld]:
    """Parse a mixture artifact's world configurations."""
    weights: dict[str, float] = payload.get("weights") or {}
    worlds_block: dict[str, dict] = payload.get("worlds") or {}
    if not worlds_block:
        raise ForecastArtifactError("computed forecast artifacts must carry world configurations")
    worlds: list[PublishedWorld] = []
    for name, weight in weights.items():
        spec = worlds_block.get(name)
        if spec is None:
            raise ForecastArtifactError(f"world {name!r} has a weight but no configuration")
        if "probs" in spec:
            raise ForecastArtifactError(
                f"world {name!r} carries precomputed probabilities; only simulator-built worlds publish "
                "the full distribution surface"
            )
        perturbations = [parse_perturbation(p) for p in spec.get("perturbations", [])]
        unpublishable = [p for p in perturbations if not spec_for(p).publishes]
        if unpublishable:
            kinds = ", ".join(sorted({type(p).name for p in unpublishable}))
            raise ForecastArtifactError(f"world {name!r} carries what-if instruments that never publish: {kinds}")
        latent = [LatentEffect.model_validate(e) for e in spec.get("latent_effects", [])]
        worlds.append(PublishedWorld(name=name, weight=weight, perturbations=perturbations, latent_effects=latent))
    for name in worlds_block:
        if name not in weights:
            raise ForecastArtifactError(f"world {name!r} has a configuration but no weight")
    total = sum(w.weight for w in worlds)
    if abs(total - 1.0) > 1e-6:
        raise ForecastArtifactError(f"world weights sum to {total:.4f}, not 1")
    return worlds


def simulate_worlds(
    forecaster: Forecaster,
    worlds: list[PublishedWorld],
    *,
    n_sims: int,
    seed: int,
    extra_results: dict[int, PlayedResult] | None = None,
) -> dict[str, SimResult]:
    """Simulate each world once with common random numbers, keeping the raw results."""
    results = forecaster.played_results(extra_results=extra_results)
    return {
        w.name: forecaster.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=tuple(w.perturbations),
            latent_effects=tuple(w.latent_effects),
            results=results,
        )
        for w in worlds
    }


def mixed_outputs(
    forecaster: Forecaster,
    worlds: list[PublishedWorld],
    *,
    n_sims: int,
    seed: int,
    extra_results: dict[int, PlayedResult] | None = None,
    per_world_results: dict[str, SimResult] | None = None,
) -> SimOutputs:
    """Mix the published probabilities by world weight; provided results are reused."""
    modal = max(worlds, key=lambda w: w.weight)
    per_world_results = per_world_results or simulate_worlds(
        forecaster, worlds, n_sims=n_sims, seed=seed, extra_results=extra_results
    )
    per_world = {
        w.name: forecaster.sim_outputs(
            n_sims=n_sims, seed=seed, extra_results=extra_results, result=per_world_results[w.name]
        )
        for w in worlds
    }
    if len(worlds) == 1:
        return per_world[modal.name]
    weights = {w.name: w.weight for w in worlds}
    mixed = per_world[modal.name].model_copy(deep=True)

    for stage in mixed.focus.finish_probs:
        mixed.focus.finish_probs[stage] = _mix(weights, per_world, lambda o, s=stage: o.focus.finish_probs[s])
    for stage in mixed.focus.reach_probs:
        mixed.focus.reach_probs[stage] = _mix(weights, per_world, lambda o, s=stage: o.focus.reach_probs[s])
    for i, team in enumerate(mixed.teams):
        team.champion_prob = _mix(weights, per_world, lambda o, j=i: o.teams[j].champion_prob)
        for stage in team.reach_probs:
            team.reach_probs[stage] = _mix(weights, per_world, lambda o, j=i, s=stage: o.teams[j].reach_probs[s])
    by_match = {name: {m.match: m for m in outputs.matches} for name, outputs in per_world.items()}
    for entry in mixed.matches:
        if not all(entry.match in by_match[name] for name in weights):
            continue
        entry.p_home = _mix(weights, per_world, lambda o, m=entry.match: _match(o, m).p_home)
        entry.p_away = _mix(weights, per_world, lambda o, m=entry.match: _match(o, m).p_away)
        if entry.p_draw is not None:
            entry.p_draw = _mix(weights, per_world, lambda o, m=entry.match: _match(o, m).p_draw or 0.0)
            total = entry.p_home + entry.p_draw + entry.p_away
            if total > 0:
                entry.p_home = round(entry.p_home / total, 6)
                entry.p_draw = round(entry.p_draw / total, 6)
                entry.p_away = round(entry.p_away / total, 6)
    return mixed


def govern_outputs(outputs: SimOutputs, anchor: SimOutputs, *, d: float) -> None:
    """Shrink the published probabilities towards the deterministic anchor in
    log-odds. Stage-by-stage blending of two monotone reach chains stays
    monotone at the magnitudes the governor produces; the governor block in
    the snapshot makes the shrink loud either way."""
    from wolves.agent.consensus import blend_log_odds

    if d == 1.0:
        return
    titles = {t.team_id: t.champion_prob for t in outputs.teams}
    anchor_titles = {t.team_id: t.champion_prob for t in anchor.teams}
    governed = blend_log_odds(titles, anchor_titles, d=d, renormalise=True)
    anchor_teams = {t.team_id: t for t in anchor.teams}
    for team in outputs.teams:
        team.champion_prob = round(governed[team.team_id], 6)
        anchor_reach = anchor_teams[team.team_id].reach_probs
        for stage, p in team.reach_probs.items():
            blended = blend_log_odds({stage: p}, {stage: anchor_reach.get(stage, p)}, d=d)
            team.reach_probs[stage] = round(blended[stage], 6)
    for stage, p in outputs.focus.reach_probs.items():
        blended = blend_log_odds({stage: p}, {stage: anchor.focus.reach_probs.get(stage, p)}, d=d)
        outputs.focus.reach_probs[stage] = round(blended[stage], 6)
    for stage, p in outputs.focus.finish_probs.items():
        blended = blend_log_odds({stage: p}, {stage: anchor.focus.finish_probs.get(stage, p)}, d=d)
        outputs.focus.finish_probs[stage] = round(blended[stage], 6)


def _mix(weights: dict[str, float], per_world: dict[str, SimOutputs], pick) -> float:
    return round(sum(weight * pick(per_world[name]) for name, weight in weights.items()), 6)


def _match(outputs: SimOutputs, match: int):
    return next(m for m in outputs.matches if m.match == match)
