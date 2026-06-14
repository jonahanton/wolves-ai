"""One-off in-place patch of the 13 Jun real agent run, injecting the
distribution-richness contract (camps, per-team stories, sourced news with
prices, market gaps, provenance, our_call/component_mean) WITHOUT changing any
published number. Mechanical fields are arithmetic on the stored sidecar; the
market-gap and news numbers are lifted once, by hand, from this run's own
reason strings and quant findings (the production no-parse rule does not bind a
hand-checked migration); the stories and impact sentences are authored from the
run's real headline, focus_story and market_justification.

Usage: STORAGE_MODE=local uv run --project engine python scripts/backfill_distribution_richness.py [snapshot.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_SNAPSHOT = Path("runs/snapshots/2026/06/13/agent-20260613-140248.json")

CAMP_OF_WORLD = {
    "model_base": "model",
    "model_evidence": "model",
    "market_base": "market",
    "market_evidence": "market",
}
CAMPS = [
    {"key": "model", "label": "Using fitted team ratings", "order": 0,
     "summary": "One strength rating per team, fit to past scorelines with recent games weighted most."},
    {"key": "market", "label": "Using market odds", "order": 1,
     "summary": "The bookmaker consensus, with the margin stripped out."},
]
CAMP_LABEL = {
    "model_base": ("model", "Model, before today's news", "Our ratings with no news applied."),
    "model_evidence": ("model", "Model, with today's news", "Our ratings once the confirmed injuries are priced in."),
    "market_base": ("market", "Markets, before today's news", "The bookmakers' view, before today's news."),
    "market_evidence": ("market", "Markets, with today's news", "The bookmakers' view once the confirmed injuries are priced in."),
}

NOISE_FLOOR_PP = 0.59

MARKET_GAPS = {
    "france": {"model_prob": 0.083, "market_prob": 0.160, "gap_pp": 7.69, "floor_multiple": 13.0},
    "england": {"model_prob": 0.072, "market_prob": 0.110, "gap_pp": 3.87, "floor_multiple": 6.6},
    "portugal": {"model_prob": 0.079, "market_prob": 0.100, "gap_pp": 2.11, "floor_multiple": 3.6},
    "spain": {"model_prob": 0.184, "market_prob": 0.160, "gap_pp": 2.42, "floor_multiple": 4.1},
    "argentina": {"model_prob": 0.102, "market_prob": 0.080, "gap_pp": 2.19, "floor_multiple": 3.7},
    "germany": {"model_prob": 0.064, "market_prob": 0.052, "gap_pp": 1.19, "floor_multiple": 2.0},
    "colombia": {"model_prob": 0.049, "market_prob": 0.016, "gap_pp": 3.38, "floor_multiple": 5.7},
    "belgium": {"model_prob": 0.044, "market_prob": 0.023, "gap_pp": 2.12, "floor_multiple": 3.6},
}

PRICED = {
    "led-0002": {"signed_delta_pp": -2.47, "material": True},
    "led-0001": {"signed_delta_pp": -0.77, "material": True},
    "led-0003": {"signed_delta_pp": 1.89, "material": True},
    "led-0008": {"signed_delta_pp": 0.90, "material": True},
}

IMPACTS = {
    "led-0002": "Losing two midfielders for the tournament thins a side whose strength runs through the middle, so we mark the Netherlands down clearly though not severely.",
    "led-0001": "Endo's withdrawal removes Japan's midfield anchor, a real loss but one good cover can soften, so the mark-down stays small.",
    "led-0003": "Neuer back in full training restores Germany's first-choice keeper, a steadying lift rather than a transformation, so the move up is modest.",
    "led-0008": "Martinez passing his medical clears the one doubt over Argentina's goal, so the small uplift just removes a risk the market had already half-priced.",
}

TEAM_STORIES = {
    "spain": {
        "summary": "Spain are the favourites, with Rodri fit and Yamal back from injury.",
        "why": "Rodri is back at full fitness and Yamal has recovered from injury, so nothing this week weakens Spain. Our ratings put them at 18% and the market at 16%, both clear of the field, and we land at 16%.",
    },
    "france": {
        "summary": "France are the closest challengers to Spain, the market backing them well above our ratings.",
        "why": "Our ratings put France near 8% on recent results, but the market has backed them at 16% all month, reading in a big-tournament pedigree the ratings can't measure. We trust the market more here and land at 14%, between the two.",
    },
    "portugal": {
        "summary": "Portugal are genuine semi-final contenders, a little ahead of our ratings.",
        "why": "Our ratings have Portugal at 8% and the market a little higher at 10%; we lean towards the market and land at 9%. No injuries or selection news touched them this week.",
    },
    "england": {
        "summary": "England are genuine semi-final contenders, backed by squad depth.",
        "why": "Our ratings have England at 7% on recent results, the market higher at 11%, reading in the strength and depth of the squad. We trust the market more and land at 10%, just behind the top group.",
    },
    "argentina": {
        "summary": "Argentina are the strongest South American side, with Martinez fit again in goal.",
        "why": "Emiliano Martinez has recovered from a fractured finger and is cleared to play, lifting Argentina slightly. Our ratings rate them higher than the market, 11% against 8%, and we land at 9% between the two.",
    },
    "brazil": {
        "summary": "Brazil stay in the leading pack despite an opening-match doubt.",
        "why": "Neymar misses the opening match and Alisson is easing back from injury, but neither changes Brazil's overall chances much. Our ratings and the market almost agree, at 9%, and we land there.",
    },
    "germany": {
        "summary": "Germany are mid-pack contenders, with Neuer fit again after a calf injury.",
        "why": "Neuer has recovered from a calf injury and is training fully again, a small boost. Our ratings have Germany at 7% and the market lower at 5%; we lean towards the market and land at 6%.",
    },
    "netherlands": {
        "summary": "The Netherlands open shorthanded after two midfielders were ruled out.",
        "why": "Xavi Simons and Jerdy Schouten are both out for the tournament with knee injuries, which lowers our estimate. Beyond that our ratings and the market agree, leaving the Netherlands at 4%.",
    },
    "japan": {
        "summary": "Japan open shorthanded after losing two key players.",
        "why": "Wataru Endo and Kaoru Mitoma are both out of the squad injured, weakening Japan's midfield and attack. The losses lower their chances a little, though there is enough cover to keep the fall small.",
    },
}

NUMERIC_TEAM_FIELDS = ("champion_prob", "elo", "rating", "value_eur_m")


def _numeric_fingerprint(snapshot: dict) -> dict:
    """The published numbers the backfill must never touch."""
    teams = {t["team_id"]: {k: t.get(k) for k in NUMERIC_TEAM_FIELDS} for t in snapshot["teams"]}
    weights = {w["name"]: w["weight"] for w in snapshot["agent"]["worlds"]}
    return {"teams": teams, "weights": weights}


def _sidecar_fingerprint(sidecar: dict) -> dict:
    return {
        team: {stage: {"bin_edges": c["bin_edges"], "histogram": c["histogram"], "world_bins": c["world_bins"]}
               for stage, c in stages.items()}
        for team, stages in sidecar["teams"].items()
    }


def _camp_probs(components: dict) -> dict[str, float]:
    num: dict[str, float] = {}
    den: dict[str, float] = {}
    for world, c in components.items():
        camp = CAMP_OF_WORLD.get(world, world)
        num[camp] = num.get(camp, 0.0) + c["weight"] * c["mean"]
        den[camp] = den.get(camp, 0.0) + c["weight"]
    return {camp: round(num[camp] / den[camp], 6) for camp in num if den[camp] > 0}


def _news_for(team: str, ledger: list[dict]) -> list[dict]:
    out: list[dict] = []
    for e in ledger:
        if e.get("team_id") != team:
            continue
        price = PRICED.get(e["id"])
        out.append({
            "ledger_id": e["id"],
            "claim": e["claim"],
            "mechanism": e["mechanism"],
            "source_url": e["source_url"],
            "title": e.get("title"),
            "hostname": urlparse(e["source_url"]).hostname or "",
            "status": e["status"],
            "signed_delta_pp": price["signed_delta_pp"] if price else None,
            "material": price["material"] if price else False,
            "excluded_reason": None,
            "impact": IMPACTS.get(e["id"]),
        })
    return out


def _build_drivers(snapshot: dict, sidecar: dict) -> dict:
    ledger = snapshot["agent"]["ledger_entries"]
    teams = {e["team_id"] for e in ledger if e.get("team_id")} | set(MARKET_GAPS)
    drivers: dict[str, dict] = {}
    for team in teams:
        cell = sidecar["teams"].get(team, {}).get("champion")
        camp_probs = _camp_probs(cell["components"]) if cell else {}
        news = _news_for(team, ledger)
        gap = MARKET_GAPS.get(team)
        market_gap = None
        if gap:
            market_gap = {"team_id": team, **gap,
                          "direction": "market_higher" if gap["market_prob"] >= gap["model_prob"] else "market_lower"}
        means = [c["mean"] for c in cell["components"].values()] if cell else []
        has_story = market_gap is not None or any(n["material"] for n in news)
        drivers[team] = {
            "camp_probs": camp_probs,
            "market_gap": market_gap,
            "news": news,
            "has_story": has_story,
            "higher_camp": max(camp_probs, key=camp_probs.get) if has_story and camp_probs else None,
            "spread_pp": round((max(means) - min(means)) * 100, 2) if means else 0.0,
            "noise_floor_pp": NOISE_FLOOR_PP,
        }
    return drivers


def backfill(snapshot_path: Path) -> None:
    dist_path = snapshot_path.with_suffix(".distributions.json")
    snapshot = json.loads(snapshot_path.read_text())
    sidecar = json.loads(dist_path.read_text())
    before = _numeric_fingerprint(snapshot)
    before_sidecar = _sidecar_fingerprint(sidecar)

    agent = snapshot["agent"]
    for w in agent["scenario_weights"]:
        camp, label, summary = CAMP_LABEL.get(w["name"], ("", "", ""))
        w["camp"], w["label"], w["summary"] = camp, label, summary
    camp_weight: dict[str, float] = {}
    for w in agent["scenario_weights"]:
        camp_weight[w["camp"] or w["name"]] = camp_weight.get(w["camp"] or w["name"], 0.0) + w["weight"]
    agent["camps"] = [{**c, "weight": round(camp_weight.get(c["key"], 0.0), 6)} for c in CAMPS]
    agent["narrative"]["team_stories"] = TEAM_STORIES
    agent["provenance"] = {
        "news_considered": len(agent["ledger_entries"]),
        "news_material": sum(1 for p in PRICED.values() if p["material"]),
        "news_excluded": 2,
        "market_disagreements": len(MARKET_GAPS),
        "noise_floor_pp": NOISE_FLOOR_PP,
        "n_worlds": len(agent["worlds"]),
        "n_camps": len(CAMPS),
    }

    champ = {t["team_id"]: t["champion_prob"] for t in snapshot["teams"]}
    for team, stages in sidecar["teams"].items():
        cell = stages.get("champion")
        if cell is None:
            continue
        cell["component_mean"] = round(sum(c["weight"] * c["mean"] for c in cell["components"].values()), 6)
        cell["our_call"] = round(champ[team], 6) if team in champ else None
    snapshot["distributions"]["drivers"] = _build_drivers(snapshot, sidecar)

    if _numeric_fingerprint(snapshot) != before:
        raise SystemExit("backfill changed a published number; aborting without writing")
    if _sidecar_fingerprint(sidecar) != before_sidecar:
        raise SystemExit("backfill changed a sidecar histogram; aborting without writing")

    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    dist_path.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(f"backfilled {snapshot_path.name}: {len(snapshot['distributions']['drivers'])} drivers, "
          f"{len(TEAM_STORIES)} stories, {len(MARKET_GAPS)} market gaps; published numbers unchanged")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
    backfill(path)


if __name__ == "__main__":
    main()
