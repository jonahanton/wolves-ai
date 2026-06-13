"""Scenario mixtures as one latent-variable model.

Flat scenario lists and factor blocks both reduce to a lattice of worlds.
Independent factors compose as weight products; a joint table reweights the
same conditionals; enumeration is exact up to a small lattice and the
mixture artifact persists worlds, conditionals, per-factor marginals and
the paired-seed noise floor so the attribution is honest by construction."""

from __future__ import annotations

import json
from itertools import product
from typing import Any

from pydantic import BaseModel, Field

from wolves.forecast import Perturbation
from wolves.quant.wolves_quant._sim import baseline, noise_floor, simulate
from wolves.quant.wolves_quant._state import SESSION, context
from wolves.sim.latent import LatentEffect

ENUMERATION_LIMIT = 24


class Scenario(BaseModel):
    """One named causal world: a sim configuration or a precomputed distribution."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    weight: float
    perturbations: list[Perturbation] = Field(default_factory=list)
    latent_effects: list[LatentEffect] = Field(default_factory=list)
    probs: dict[str, float] | None = None


class Factor(BaseModel):
    """One independent uncertainty source with weighted variants."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    variants: list[Scenario]


class MixtureWeightError(ValueError):
    def __init__(self, what: str, total: float) -> None:
        super().__init__(f"{what} weights sum to {total:.4f}, not 1")


class MixtureSizeError(ValueError):
    def __init__(self, worlds: int) -> None:
        super().__init__(
            f"the factor lattice has {worlds} worlds, beyond the enumeration limit {ENUMERATION_LIMIT}; "
            "coarsen a factor or integrate by sampling magnitudes inside fewer worlds"
        )


def scenario_mixture(
    scenarios: list[Scenario | dict[str, Any]] | None = None,
    *,
    factors: list[Factor | dict[str, Any]] | None = None,
    joint: dict[str, float] | None = None,
    n_sims: int | None = None,
    seed: int = 0,
    name: str = "mixture",
) -> dict[str, Any]:
    """Integrate a scenario mixture and persist it as a submit-ready artifact.

    Pass scenarios for a flat mixture, or factors for a product lattice;
    joint overrides the independence product with explicit world weights
    keyed "variantA|variantB". Returns mixture, per-world conditionals,
    per-factor marginals and the noise floor; writes outputs/<name>.json."""
    # The submission candidate prices at publish fidelity, never the cheap
    # exploration default.
    n_sims = n_sims or max(context().default_n_sims, 50_000)
    blocks = _factor_blocks(scenarios, factors)
    worlds = _worlds(blocks, joint)
    total = sum(w for _, w, _ in worlds)
    if abs(total - 1.0) > 1e-6:
        raise MixtureWeightError("world", total)

    base = baseline(n_sims=n_sims, seed=seed)
    conditionals: dict[str, dict[str, float]] = {}
    mixture: dict[str, float] = dict.fromkeys(base, 0.0)
    for key, weight, scenario_parts in worlds:
        probs = _world_probs(scenario_parts, n_sims=n_sims, seed=seed)
        conditionals[key] = probs
        for team, p in probs.items():
            mixture[team] = mixture.get(team, 0.0) + weight * p

    result = {
        "name": name,
        "weights": {key: weight for key, weight, _ in worlds},
        # World configurations make the published distribution reproducible:
        # the harness re-simulates each world from these at publish time.
        "worlds": {
            key: {
                "perturbations": [p.model_dump(mode="json") for s in parts for p in s.perturbations],
                **(
                    {"latent_effects": [e.model_dump(mode="json") for s in parts for e in s.latent_effects]}
                    if any(s.latent_effects for s in parts)
                    else {}
                ),
                **({"probs": parts[0].probs} if parts[0].probs is not None else {}),
            }
            for key, _, parts in worlds
        },
        "mixture": mixture,
        "conditionals": conditionals,
        "marginals": _marginals(blocks, worlds, conditionals),
        "baseline": base,
        "noise_floor_pp": noise_floor(n_sims=n_sims, seed=seed),
        "n_sims": n_sims,
        "seed": seed,
    }
    out = SESSION.root / "outputs" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    result["artifact_file"] = str(out.relative_to(SESSION.root))
    return result


def _factor_blocks(
    scenarios: list[Scenario | dict[str, Any]] | None,
    factors: list[Factor | dict[str, Any]] | None,
) -> list[Factor]:
    if (scenarios is None) == (factors is None):
        raise ValueError("pass exactly one of scenarios or factors")
    if scenarios is not None:
        flat = [s if isinstance(s, Scenario) else Scenario.model_validate(s) for s in scenarios]
        return [Factor(name="scenario", variants=flat)]
    assert factors is not None
    return [f if isinstance(f, Factor) else Factor.model_validate(f) for f in factors]


def _worlds(blocks: list[Factor], joint: dict[str, float] | None) -> list[tuple[str, float, tuple[Scenario, ...]]]:
    for block in blocks:
        total = sum(v.weight for v in block.variants)
        if joint is None and abs(total - 1.0) > 1e-6:
            raise MixtureWeightError(f"factor {block.name!r}", total)
    count = 1
    for block in blocks:
        count *= len(block.variants)
    if count > ENUMERATION_LIMIT:
        raise MixtureSizeError(count)
    combos = list(product(*(block.variants for block in blocks)))
    keys = ["|".join(v.name for v in combo) for combo in combos]
    if joint is not None and set(joint) != set(keys):
        raise ValueError(f"joint keys must cover the lattice exactly: {sorted(keys)}")
    return [
        (key, joint[key] if joint is not None else _product(v.weight for v in combo), combo)
        for key, combo in zip(keys, combos, strict=True)
    ]


def _world_probs(parts: tuple[Scenario, ...], *, n_sims: int | None, seed: int) -> dict[str, float]:
    fixed = [s.probs for s in parts if s.probs is not None]
    if fixed:
        if len(parts) > 1:
            raise ValueError("precomputed probs only combine in a flat scenario list, not a factor product")
        return fixed[0]
    perturbations: list[Perturbation] = [p for s in parts for p in s.perturbations]
    latent: list[LatentEffect] = [e for s in parts for e in s.latent_effects]
    return simulate(perturbations, latent_effects=latent, n_sims=n_sims, seed=seed)


def _marginals(
    blocks: list[Factor],
    worlds: list[tuple[str, float, tuple[Scenario, ...]]],
    conditionals: dict[str, dict[str, float]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Per-factor marginal conditionals: the attribution and noise check in one."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    for i, block in enumerate(blocks):
        variants: dict[str, dict[str, float]] = {}
        for variant in block.variants:
            members = [(k, w) for k, w, combo in worlds if combo[i].name == variant.name]
            mass = sum(w for _, w in members)
            if mass <= 0:
                continue
            marginal: dict[str, float] = {}
            for key, w in members:
                for team, p in conditionals[key].items():
                    marginal[team] = marginal.get(team, 0.0) + (w / mass) * p
            variants[variant.name] = marginal
        out[block.name] = variants
    return out


def _product(values: Any) -> float:
    result = 1.0
    for v in values:
        result *= v
    return result
