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
from wolves.run_agent import _camp_probs
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.latent import LatentEffect, SpikeSlabPrior
from wolves.snapshot import (
    AgentBlock,
    CampOut,
    MarketGapOut,
    MarketsBlock,
    NarrativeBlock,
    NewsItemOut,
    ProvenanceOut,
    RunMeta,
    ScenarioWeightOut,
    Snapshot,
    TeamDriver,
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


def _drivers(spec, per_world_champion, weights, camp_of, noise_floor_pp) -> dict[str, TeamDriver]:
    out: dict[str, TeamDriver] = {}
    for team, d in spec.items():
        camp_probs = _camp_probs(team, per_world_champion, weights, camp_of)
        news = [NewsItemOut(**n) for n in d.get("news", [])]
        gap = d.get("market_gap")
        market_gap = MarketGapOut(**gap) if gap else None
        means = [champ.get(team, 0.0) for champ in per_world_champion.values()]
        out[team] = TeamDriver(
            camp_probs=camp_probs,
            market_gap=market_gap,
            news=news,
            has_story=market_gap is not None or any(n.material for n in news),
            higher_camp=max(camp_probs, key=camp_probs.get) if camp_probs else None,
            spread_pp=round((max(means) - min(means)) * 100, 2) if means else 0.0,
            noise_floor_pp=noise_floor_pp,
        )
    return out


def _build(
    fc: Forecaster, run_id, when, worlds, narrative, scenario_weights, camps, driver_spec, *, seed, noise_floor_pp
) -> tuple[Snapshot, dict]:
    per_world = simulate_worlds(fc, worlds, n_sims=N_SIMS, seed=seed)
    outputs = mixed_outputs(fc, worlds, n_sims=N_SIMS, seed=seed, per_world_results=per_world)
    weights = {w.name: w.weight for w in worlds}
    champion_prob = {t.team_id: t.champion_prob for t in outputs.teams}
    distributions, sidecars = build_run_distributions(
        fc.fmt, per_world, weights, settings=fc._settings, played=frozenset(), rng_seed=seed, champion_prob=champion_prob
    )
    per_world_champion = {
        w.name: {t.team_id: t.champion_prob for t in fc.sim_outputs(n_sims=N_SIMS, seed=seed, result=per_world[w.name]).teams}
        for w in worlds
    }
    camp_of = {sw["name"]: (sw.get("camp") or sw["name"]) for sw in scenario_weights}
    camp_weight: dict[str, float] = {}
    for sw in scenario_weights:
        key = sw.get("camp") or sw["name"]
        camp_weight[key] = camp_weight.get(key, 0.0) + sw["weight"]
    camps = [{**c, "weight": round(camp_weight.get(c["key"], 0.0), 6)} for c in camps]
    distributions.drivers = _drivers(driver_spec, per_world_champion, weights, camp_of, noise_floor_pp)
    match_probs = _world_match_probs(fc, per_world, seed=seed)
    agent = AgentBlock(
        narrative=NarrativeBlock(**narrative),
        artifact_id=f"mixture-{run_id[-3:]}",
        ledger_entries=[],
        scenario_weights=[ScenarioWeightOut(**sw) for sw in scenario_weights],
        camps=[CampOut(**c) for c in camps],
        worlds=[
            WorldOut(
                name=w.name,
                weight=w.weight,
                perturbations=[p.model_dump(mode="json") for p in w.perturbations],
                latent_effects=[e.model_dump(mode="json") for e in w.latent_effects],
                title_probs=_top_probs(per_world_champion[w.name]),
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
        provenance=ProvenanceOut(
            news_considered=sum(len(d.get("news", [])) for d in driver_spec.values()),
            news_material=sum(1 for d in driver_spec.values() for n in d.get("news", []) if n.get("material")),
            news_excluded=sum(1 for d in driver_spec.values() for n in d.get("news", []) if n.get("excluded_reason")),
            market_disagreements=sum(1 for d in driver_spec.values() if d.get("market_gap")),
            noise_floor_pp=noise_floor_pp,
            n_worlds=len(worlds),
            n_camps=len({c["key"] for c in camps}) or len(worlds),
        ),
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
     "rationale": "Quiet day: the fitted model anchors the forecast with no fresh material news.",
     "camp": "model", "label": "Our statistical model", "summary": "What our ratings say from qualifying form alone."},
    {"name": "market_lean", "weight": 0.45, "scenario_id": None, "ledger_ids": [],
     "rationale": "A light market premium on the top three, well inside the noise; nothing contested today.",
     "camp": "market", "label": "The betting markets", "summary": "Where the bookmakers price the top three."},
]
QUIET_CAMPS = [
    {"key": "model", "label": "Our statistical model", "summary": "What our ratings say from qualifying form alone.", "order": 0},
    {"key": "market", "label": "The betting markets", "summary": "Where the bookmakers price each team.", "order": 1},
]
QUIET_NARRATIVE = {
    "headline": "A settled day at the top. Spain remain favourites with France and England close behind. No fresh news moves the contenders.",
    "focus_story": "England hold their position as clear semi-final contenders on a quiet day with no squad news.",
    "slot_rationales": {}, "travel_memo": "No travel implications today.",
    "team_stories": {
        "spain": {"summary": "Spain stay clear favourites on a quiet day.",
                  "why": "Nothing fresh moved Spain today. The model and the markets agree they are the team to beat, and we leave them on top."},
        "england": {"summary": "England hold as clear semi-final contenders.",
                    "why": "No squad news for England today. A light market premium keeps them just behind the top two, where our model also has them."},
    },
}
QUIET_DRIVERS = {}

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
     "rationale": "The unperturbed model, the sceptical anchor on a day with only minor news.",
     "camp": "model", "label": "Our statistical model", "summary": "What our ratings say before today's news."},
    {"name": "market_lean", "weight": 0.40, "scenario_id": None, "ledger_ids": [],
     "rationale": "A modest market premium on France and Brazil, a touch above the model and well inside reason.",
     "camp": "market", "label": "The betting markets", "summary": "Where the bookmakers price France and Brazil."},
    {"name": "injury_doubt", "weight": 0.18, "scenario_id": None, "ledger_ids": [],
     "rationale": "One Netherlands starter doubtful with uncertain depth, plus a mild shared European drift sampled per draw.",
     "camp": "news", "label": "Today's injury news", "summary": "A Netherlands starter in doubt, read through the squad."},
    {"name": "knockout_call", "weight": 0.12, "scenario_id": None, "ledger_ids": [],
     "rationale": "A slight lean that France edge Brazil should they meet in the knockouts, on the matchup read.",
     "camp": "news", "label": "Today's injury news", "summary": "A matchup lean folded in with the day's live reads."},
]
DISAGREE_CAMPS = [
    {"key": "model", "label": "Our statistical model", "summary": "What our ratings say before today's news.", "order": 0},
    {"key": "market", "label": "The betting markets", "summary": "Where the bookmakers price each team.", "order": 1},
    {"key": "news", "label": "Today's live reads", "summary": "What today's injury and matchup news shifts.", "order": 2},
]
DISAGREE_NARRATIVE = {
    "headline": "A little more disagreement than yesterday. The market nudges France and Brazil up, and a Netherlands starter is in doubt. The top of the board barely moves.",
    "focus_story": "England hold station just behind a tight top tier, with no fresh news of their own.",
    "slot_rationales": {}, "travel_memo": "No travel implications today.",
    "team_stories": {
        "france": {"summary": "France edge up on a market premium and a knockout lean.",
                   "why": "The markets price France a touch above our model, and we lean slightly their way in a possible meeting with Brazil. Together that nudges them up, though the move is small."},
        "netherlands": {"summary": "The Netherlands soften with a starter in doubt.",
                        "why": "One Netherlands starter is doubtful and their depth there is uncertain, so we mark them down a little. Otherwise our model and the markets broadly agree."},
        "england": {"summary": "England hold station just behind the top tier.",
                    "why": "No fresh news for England. They sit just behind a tight top group, where both our model and the markets place them."},
    },
}
DISAGREE_DRIVERS = {
    "france": {
        "market_gap": {"team_id": "france", "model_prob": 0.083, "market_prob": 0.13, "gap_pp": 4.7,
                       "floor_multiple": 8.0, "direction": "market_higher"},
    },
    "netherlands": {
        "news": [{"ledger_id": "synthetic-nl-1",
                  "claim": "A Netherlands starter is doubtful for the opener with depth uncertain behind him",
                  "mechanism": "One first-choice starter in doubt; cover unproven",
                  "source_url": "https://example.com/netherlands-injury",
                  "title": "Netherlands injury doubt ahead of the opener",
                  "hostname": "example.com", "status": "probable", "signed_delta_pp": -1.2,
                  "material": True, "excluded_reason": None,
                  "impact": "Losing a first-choice starter with unproven cover thins the side a little, so we mark them down modestly rather than sharply."}],
    },
}

INJURY_WORLDS = [
    PublishedWorld(name="news_out", weight=0.55,
                   perturbations=[_sp("portugal", -0.06, "key forward ruled out of the group stage")]),
    PublishedWorld(name="news_fit", weight=0.45),
]
INJURY_WEIGHTS = [
    {"name": "news_out", "weight": 0.55, "scenario_id": None, "ledger_ids": [],
     "rationale": "The medical update reads as a group-stage absence, the more likely branch on today's reporting.",
     "camp": "out", "label": "Forward ruled out", "summary": "Portugal without their key forward for the group stage."},
    {"name": "news_fit", "weight": 0.45, "scenario_id": None, "ledger_ids": [],
     "rationale": "The club has not confirmed the absence, so a meaningful chance the forward is passed fit remains.",
     "camp": "fit", "label": "Forward passed fit", "summary": "Portugal at full strength if he recovers in time."},
]
INJURY_CAMPS = [
    {"key": "out", "label": "Forward ruled out", "summary": "Portugal without their key forward for the group stage.", "order": 0},
    {"key": "fit", "label": "Forward passed fit", "summary": "Portugal at full strength if he recovers in time.", "order": 1},
]
INJURY_NARRATIVE = {
    "headline": "A Portugal injury splits the day. Their key forward looks set to miss the group stage, which pulls them back, though there is still a chance he is passed fit.",
    "focus_story": "England are unaffected by the day's news and hold their place in the chasing pack.",
    "slot_rationales": {}, "travel_memo": "No travel implications today.",
    "team_stories": {
        "portugal": {"summary": "Portugal split on whether their forward plays.",
                     "why": "Their key forward looks likely to miss the group stage, which pulls Portugal back. We keep real weight on him being passed fit, so the number sits between the two."},
        "england": {"summary": "England are unaffected and hold their place.",
                    "why": "Nothing in today's Portugal news touches England. They hold their place in the chasing pack on the model."},
    },
}
INJURY_DRIVERS = {
    "portugal": {
        "news": [{"ledger_id": "synthetic-por-1",
                  "claim": "Portugal's key forward is in doubt for the group stage with a muscle injury",
                  "mechanism": "Primary goal threat out for the group stage; attack leans on cover",
                  "source_url": "https://example.com/portugal-forward-injury",
                  "title": "Portugal sweat on forward's fitness", "hostname": "example.com",
                  "status": "probable", "signed_delta_pp": -2.1, "material": True, "excluded_reason": None,
                  "impact": "Losing the side's main goal threat for the group stage lowers their ceiling, so the absence branch sits clearly below the fit one."}],
    },
}


def main() -> None:
    fc = _forecaster()
    quiet = _build(fc, "agent-20260611-090000", "2026-06-11T09:00:00+00:00", QUIET_WORLDS, QUIET_NARRATIVE,
                   QUIET_WEIGHTS, QUIET_CAMPS, QUIET_DRIVERS, seed=11, noise_floor_pp=0.55)
    _publish(fc, *quiet, as_of=date(2026, 6, 11))
    disagree = _build(fc, "agent-20260612-090000", "2026-06-12T09:00:00+00:00", DISAGREE_WORLDS, DISAGREE_NARRATIVE,
                      DISAGREE_WEIGHTS, DISAGREE_CAMPS, DISAGREE_DRIVERS, seed=12, noise_floor_pp=0.61)
    _publish(fc, *disagree, as_of=date(2026, 6, 12))
    injury = _build(fc, "agent-20260610-090000", "2026-06-10T09:00:00+00:00", INJURY_WORLDS, INJURY_NARRATIVE,
                    INJURY_WEIGHTS, INJURY_CAMPS, INJURY_DRIVERS, seed=10, noise_floor_pp=0.58)
    _publish(fc, *injury, as_of=date(2026, 6, 10))


if __name__ == "__main__":
    main()
