"""Emit synthetic full agent-run outputs (snapshot + four sidecars) for frontend plotting.

No LLM: hand-authored worlds are pushed through the real publish-path assembly, so the
JSON is byte-shape identical to a live agent run. The two runs give the charts more than
the single real run to plot against: a quiet day and a slightly-more-disagreement day, both
at realistic magnitudes (under ~1pp deviation from the model baseline). They are NOT
forecasts and must never be presented as real predictions; only genuine agent runs are.

The synthetic markets block is a deterministic tilt of the model probs, not real odds, and
is written only into these synthetic runs; a real run's markets block must come from the
live feed at its own timestamp.

Usage: STORAGE_MODE=local uv run --project engine python scripts/make_synthetic_runs.py
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import numpy as np

from wolves.agent.forecast_artifact import PublishedWorld, mixed_outputs, simulate_worlds
from wolves.config import Settings
from wolves.forecast import DeltaDistribution, Forecaster, KnockoutOutcome, StrengthPerturbation
from wolves.models.contracts import DatasetHandle
from wolves.publish_distributions import build_run_distributions
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.latent import LatentEffect, SpikeSlabPrior
from wolves.snapshot import (
    AgentBlock,
    MarketsBlock,
    NarrativeBlock,
    RunMeta,
    ScenarioWeightOut,
    Snapshot,
    WorldOut,
)

N_SIMS = 50_000
AS_OF_FIT = date(2026, 6, 13)


def _forecaster() -> Forecaster:
    dataset_id = json.loads(Path("runs/datasets/latest.json").read_text())["dataset_id"]
    settings = Settings(_env_file=None, storage_mode="local")
    handle = DatasetHandle(path=Path(f"runs/datasets/wolves-data-{dataset_id}.duckdb"), dataset_id=dataset_id)
    fc = Forecaster(settings, dataset=handle)
    fc.fit(as_of=AS_OF_FIT)
    return fc


def _sp(team: str, delta: float | DeltaDistribution, reason: str) -> StrengthPerturbation:
    return StrengthPerturbation(team=team, delta=delta, reason=reason)


def _top_probs(probs: dict[str, float], limit: int = 10) -> dict[str, float]:
    return dict(sorted(probs.items(), key=lambda kv: -kv[1])[:limit])


def _synth_markets(model_probs: dict[str, float], *, weight: float, tilt_seed: int) -> MarketsBlock:
    rng = np.random.default_rng(tilt_seed)
    market = {t: max(p * float(np.exp(rng.normal(0.0, 0.18))), 1e-5) for t, p in model_probs.items()}
    total = sum(market.values())
    market = {t: p / total for t, p in market.items()}
    blend = {t: (1 - weight) * model_probs[t] + weight * market[t] for t in model_probs}
    return MarketsBlock(model_probs=model_probs, market_probs=market, blend_probs=blend, model_weight=1 - weight)


def _world_match_probs(fc: Forecaster, per_world_results: dict, *, seed: int) -> dict:
    out: dict[str, dict] = {}
    for name, result in per_world_results.items():
        outputs = fc.sim_outputs(n_sims=N_SIMS, seed=seed, result=result)
        out[name] = {
            str(m.match): {"home": m.p_home, "draw": m.p_draw, "away": m.p_away}
            for m in outputs.matches
            if m.stage == "group" and m.p_draw is not None
        }
    return out


def _build(fc: Forecaster, run_id, when, worlds, narrative, scenario_weights, *, seed) -> tuple[Snapshot, dict]:
    per_world = simulate_worlds(fc, worlds, n_sims=N_SIMS, seed=seed)
    outputs = mixed_outputs(fc, worlds, n_sims=N_SIMS, seed=seed, per_world_results=per_world)
    weights = {w.name: w.weight for w in worlds}
    distributions, sidecars = build_run_distributions(
        fc.fmt, per_world, weights, settings=fc._settings, played=frozenset(), rng_seed=seed
    )
    conditionals = {
        w.name: {t.team_id: t.champion_prob for t in fc.sim_outputs(n_sims=N_SIMS, seed=seed, result=per_world[w.name]).teams}
        for w in worlds
    }
    match_probs = _world_match_probs(fc, per_world, seed=seed)
    agent = AgentBlock(
        narrative=NarrativeBlock(**narrative),
        artifact_id=f"mixture-{run_id[-3:]}",
        ledger_entries=[],
        scenario_weights=[ScenarioWeightOut(**sw) for sw in scenario_weights],
        worlds=[
            WorldOut(
                name=w.name,
                weight=w.weight,
                perturbations=[p.model_dump(mode="json") for p in w.perturbations],
                latent_effects=[e.model_dump(mode="json") for e in w.latent_effects],
                title_probs=_top_probs(conditionals[w.name]),
                match_probs=match_probs.get(w.name, {}),
            )
            for w in worlds
        ],
        escalations=[],
        market_justification="",
        change_justification="",
        inconsistency_note="",
        attribution=None,
        governor=None,
        calibration=None,
    )
    model_probs = {t.team_id: t.champion_prob for t in outputs.teams}
    snapshot = Snapshot(
        run=RunMeta(run_id=run_id, created_at=when, as_of=when[:10], n_sims=N_SIMS, engine_version="synthetic", kind="agent"),
        focus=outputs.focus,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
        agent=agent,
        markets=_synth_markets(model_probs, weight=0.45, tilt_seed=seed),
        distributions=distributions,
    )
    return snapshot, sidecars


def _publish(fc: Forecaster, snapshot: Snapshot, sidecars: dict, *, as_of: date) -> None:
    SnapshotPublisher(fc._settings).publish(snapshot, as_of=as_of, started=time.monotonic(), sidecars=sidecars)
    print(f"published {snapshot.run.run_id}: {len(snapshot.agent.worlds)} worlds, {len(sidecars)} sidecars")


QUIET_WORLDS = [
    PublishedWorld(name="model_base", weight=0.55),
    PublishedWorld(
        name="market_lean",
        weight=0.45,
        perturbations=[
            _sp("spain", 0.04, "mild market premium"),
            _sp("france", 0.03, "mild market premium"),
            _sp("england", 0.02, "market premium"),
        ],
    ),
]
QUIET_WEIGHTS = [
    {"name": "model_base", "weight": 0.55, "scenario_id": None, "ledger_ids": [],
     "rationale": "Quiet day: the fitted model anchors the forecast with no fresh material news."},
    {"name": "market_lean", "weight": 0.45, "scenario_id": None, "ledger_ids": [],
     "rationale": "A light market premium on the top three, well inside the noise; nothing contested today."},
]
QUIET_NARRATIVE = {
    "headline": "A settled day at the top. Spain remain favourites with France and England close behind. No fresh news moves the contenders.",
    "focus_story": "England hold their position as clear semi-final contenders on a quiet day with no squad news.",
    "slot_rationales": {}, "travel_memo": "No travel implications today.",
}

DISAGREE_WORLDS = [
    PublishedWorld(name="model_base", weight=0.30),
    PublishedWorld(
        name="market_lean",
        weight=0.40,
        perturbations=[
            _sp("france", 0.05, "modest market premium"),
            _sp("brazil", 0.03, "slight market premium"),
            _sp("argentina", -0.03, "slight market discount"),
        ],
    ),
    PublishedWorld(
        name="injury_doubt",
        weight=0.18,
        perturbations=[_sp("netherlands", DeltaDistribution(mean=-0.05, sd=0.03), "one starter doubtful, depth uncertain")],
        latent_effects=[
            LatentEffect(
                reason="mild shared European form drift",
                targets={"france": 0.5, "germany": 0.5, "england": 0.5, "spain": 0.5},
                prior=SpikeSlabPrior(p_zero=0.6, mean=0.03, sd=0.02),
            )
        ],
    ),
    PublishedWorld(
        name="knockout_call",
        weight=0.12,
        perturbations=[
            KnockoutOutcome(team="france", opponent="brazil", p_advance=0.56,
                            reason="slight France matchup edge over Brazil if they meet")
        ],
    ),
]
DISAGREE_WEIGHTS = [
    {"name": "model_base", "weight": 0.30, "scenario_id": None, "ledger_ids": [],
     "rationale": "The unperturbed model, the sceptical anchor on a day with only minor news."},
    {"name": "market_lean", "weight": 0.40, "scenario_id": None, "ledger_ids": [],
     "rationale": "A modest market premium on France and Brazil, a touch above the model and well inside reason."},
    {"name": "injury_doubt", "weight": 0.18, "scenario_id": None, "ledger_ids": [],
     "rationale": "One Netherlands starter doubtful with uncertain depth, plus a mild shared European drift sampled per draw."},
    {"name": "knockout_call", "weight": 0.12, "scenario_id": None, "ledger_ids": [],
     "rationale": "A slight lean that France edge Brazil should they meet in the knockouts, on the matchup read."},
]
DISAGREE_NARRATIVE = {
    "headline": "A little more disagreement than yesterday. The market nudges France and Brazil up, and a Netherlands starter is in doubt. The top of the board barely moves.",
    "focus_story": "England hold station just behind a tight top tier, with no fresh news of their own.",
    "slot_rationales": {}, "travel_memo": "No travel implications today.",
}


def main() -> None:
    fc = _forecaster()
    quiet = _build(fc, "agent-20260611-090000", "2026-06-11T09:00:00+00:00", QUIET_WORLDS, QUIET_NARRATIVE, QUIET_WEIGHTS, seed=11)
    _publish(fc, *quiet, as_of=date(2026, 6, 11))
    disagree = _build(fc, "agent-20260612-090000", "2026-06-12T09:00:00+00:00", DISAGREE_WORLDS, DISAGREE_NARRATIVE, DISAGREE_WEIGHTS, seed=12)
    _publish(fc, *disagree, as_of=date(2026, 6, 12))


if __name__ == "__main__":
    main()
