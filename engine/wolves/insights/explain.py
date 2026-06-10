"""Why the model rates a team where it does: the fitted strength decomposed
into the weighted results that pull it, plus the context the model ignores.
The pull of one match is its likelihood-gradient contribution: decay weight
times (goals scored minus expected, plus expected conceded minus conceded)."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from wolves.data.query import DatasetQuery
from wolves.data.teams import registry_team_key
from wolves.forecast import Forecaster
from wolves.models.poisson import load_fit_data

INFLUENCES_SHOWN = 15


class MatchInfluence(BaseModel):
    date: str
    opponent: str
    venue: str
    score: str
    tournament: str
    importance: float
    decay_weight: float
    expected_for: float
    expected_against: float
    pull: float
    pull_share: float


class WeightedRecord(BaseModel):
    matches: int
    weighted_wins: float
    weighted_draws: float
    weighted_losses: float
    weighted_goals_for: float
    weighted_goals_against: float


class StrengthExplanation(BaseModel):
    team: str
    strength: float
    strength_std: float
    model_rank: int
    n_ranked_teams: int
    expected_goals_vs_average: float
    expected_conceded_vs_average: float
    weighted_record: WeightedRecord
    strongest_pulls_up: list[MatchInfluence]
    strongest_pulls_down: list[MatchInfluence]
    elo_trajectory: list[dict]
    squad_value_eur_m: float | None


def model_explain(forecaster: Forecaster, team: str) -> StrengthExplanation:
    state = forecaster.state
    key = registry_team_key(team)
    state_index = {name: i for i, name in enumerate(state.teams)}
    team_pos = state_index[key]

    data = load_fit_data(
        forecaster.dataset,
        as_of=state.as_of,
        half_life_days=state.globals_["half_life_days"],
        min_importance=forecaster.model.min_importance,
    )
    diff = state.strengths[data.home_idx] - state.strengths[data.away_idx]
    lam_home = np.exp(state.globals_["intercept"] + diff + state.globals_["home_adv"] * data.at_home)
    lam_away = np.exp(state.globals_["intercept"] - diff)

    influences: list[MatchInfluence] = []
    record = {"w": 0.0, "d": 0.0, "l": 0.0, "gf": 0.0, "ga": 0.0, "n": 0}
    for i in range(data.weights.shape[0]):
        if data.home_idx[i] == team_pos:
            opponent = data.teams[data.away_idx[i]]
            venue = "home" if data.at_home[i] > 0 else "neutral"
            gf, ga, ef, ea = data.home_goals[i], data.away_goals[i], lam_home[i], lam_away[i]
        elif data.away_idx[i] == team_pos:
            opponent = data.teams[data.home_idx[i]]
            venue = "away" if data.at_home[i] > 0 else "neutral"
            gf, ga, ef, ea = data.away_goals[i], data.home_goals[i], lam_away[i], lam_home[i]
        else:
            continue
        weight = float(data.weights[i])
        pull = weight * float((gf - ef) + (ea - ga))
        influences.append(
            MatchInfluence(
                date=data.dates[i],
                opponent=opponent,
                venue=venue,
                score=f"{int(gf)}-{int(ga)}",
                tournament=data.tournaments[i],
                importance=float(data.importance[i]),
                decay_weight=round(weight, 4),
                expected_for=round(float(ef), 2),
                expected_against=round(float(ea), 2),
                pull=round(pull, 4),
                pull_share=0.0,
            )
        )
        record["n"] += 1
        record["gf"] += weight * gf
        record["ga"] += weight * ga
        outcome = "w" if gf > ga else ("d" if gf == ga else "l")
        record[outcome] += weight

    total_pull = sum(abs(inf.pull) for inf in influences) or 1.0
    for inf in influences:
        inf.pull_share = round(abs(inf.pull) / total_pull, 4)
    ranked = sorted(influences, key=lambda inf: inf.pull)

    strengths = state.strengths
    order = int(np.sum(strengths > strengths[team_pos])) + 1
    avg_diff = float(strengths[team_pos] - np.median(strengths))
    intercept = state.globals_["intercept"]
    std = float(np.sqrt(state.covariance[team_pos, team_pos])) if state.covariance is not None else 0.0

    with DatasetQuery(forecaster.dataset) as query:
        trajectory = query.elo_trajectory(key)
        covariates = query.covariates(key)

    return StrengthExplanation(
        team=team,
        strength=round(float(strengths[team_pos]), 4),
        strength_std=round(std, 4),
        model_rank=order,
        n_ranked_teams=len(state.teams),
        expected_goals_vs_average=round(float(np.exp(intercept + avg_diff)), 3),
        expected_conceded_vs_average=round(float(np.exp(intercept - avg_diff)), 3),
        weighted_record=WeightedRecord(
            matches=record["n"],
            weighted_wins=round(record["w"], 2),
            weighted_draws=round(record["d"], 2),
            weighted_losses=round(record["l"], 2),
            weighted_goals_for=round(record["gf"], 2),
            weighted_goals_against=round(record["ga"], 2),
        ),
        strongest_pulls_up=ranked[-INFLUENCES_SHOWN:][::-1],
        strongest_pulls_down=ranked[:INFLUENCES_SHOWN],
        elo_trajectory=trajectory,
        squad_value_eur_m=covariates.get("squad_value_eur_m"),
    )
