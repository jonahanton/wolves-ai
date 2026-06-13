"""Continuous latent news effects, sampled per parameter-draw inside the MC loop.

Each effect is sampled once per parameter-draw from its own prior and added to
that draw's strength mean, so the band is the joint posterior of strengths and
news. The fitted covariance is never touched: news uncertainty lives in the
prior, baseline-strength uncertainty in the covariance, so the two never
double-count.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from wolves.data.teams import canonical_team_key

GLOBAL_TARGETS = ("intercept", "home_adv")


class NormalPrior(BaseModel):
    """A continuous effect of uncertain magnitude believed to occur."""

    kind: Literal["normal"] = "normal"
    mean: float
    sd: float = Field(ge=0.0)

    def sample(self, rng: np.random.Generator, draws: int) -> np.ndarray:
        return rng.normal(self.mean, self.sd, draws)


class SpikeSlabPrior(BaseModel):
    """A continuous effect that might not occur: zero with probability p_zero,
    else Normal(mean, sd). One latent carries both regime and magnitude."""

    kind: Literal["spike_slab"] = "spike_slab"
    p_zero: float = Field(ge=0.0, le=1.0)
    mean: float
    sd: float = Field(ge=0.0)

    def sample(self, rng: np.random.Generator, draws: int) -> np.ndarray:
        occurs = rng.random(draws) >= self.p_zero
        return np.where(occurs, rng.normal(self.mean, self.sd, draws), 0.0)


class MixturePrior(BaseModel):
    """A multimodal effect: pick a component per draw by weight, then sample it."""

    kind: Literal["mixture"] = "mixture"
    weights: list[float]
    components: list[NormalPrior]

    def sample(self, rng: np.random.Generator, draws: int) -> np.ndarray:
        probs = np.array(self.weights, dtype=np.float64)
        probs /= probs.sum()
        picks = rng.choice(len(self.components), size=draws, p=probs)
        # Sample every component for every draw, then select, so rng advancement
        # stays fixed regardless of which draws picked which component.
        samples = np.array([c.sample(rng, draws) for c in self.components])
        return samples[picks, np.arange(draws)]


Prior = NormalPrior | SpikeSlabPrior | MixturePrior


class LatentEffect(BaseModel):
    """A news driver sampled per draw and added to its target strength columns.

    targets maps a team slug (or "intercept"/"home_adv") to a linear weight; a
    single-team effect targets one column at weight 1, a correlated effect
    several. The same per-draw realisation hits every target, so a shared
    driver correlates the teams it names."""

    reason: str
    targets: dict[str, float]
    prior: Prior = Field(discriminator="kind")

    def model_post_init(self, _: object) -> None:
        self.targets = {
            (t if t in GLOBAL_TARGETS else canonical_team_key(t)): w for t, w in self.targets.items()
        }

    def columns(
        self, team_columns: dict[str, int], *, intercept_col: int, home_adv_col: int
    ) -> list[tuple[int, float]]:
        resolved: list[tuple[int, float]] = []
        for target, weight in self.targets.items():
            if target == "intercept":
                resolved.append((intercept_col, weight))
            elif target == "home_adv":
                resolved.append((home_adv_col, weight))
            else:
                resolved.append((team_columns[target], weight))
        return resolved
