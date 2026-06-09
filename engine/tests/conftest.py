from __future__ import annotations

from typing import Any

from wolves.agent.contracts import ForecastSubmission, Narrative, RatingOverride

R32_MATCHES = [str(m) for m in range(73, 89)]


def build_narrative(**overrides: Any) -> Narrative:
    fields: dict[str, Any] = {
        "england_story": "England are settled and the squad trained in full ahead of Croatia.",
        "slot_rationales": {m: f"Slot {m}: favourite advances on rating gap." for m in R32_MATCHES},
        "travel_memo": "Win the group and England stay east; second means a longer hop west.",
    }
    fields.update(overrides)
    return Narrative(**fields)


def build_submission(**overrides: Any) -> ForecastSubmission:
    fields: dict[str, Any] = {
        "rating_overrides": [
            RatingOverride(
                team_id="england",
                delta_elo=15.0,
                cause="First-choice keeper confirmed fit",
                ledger_ids=["led-0001"],
            )
        ],
        "england_reach_probs": {
            "r32": 0.97,
            "r16": 0.62,
            "qf": 0.38,
            "sf": 0.22,
            "final": 0.13,
            "champion": 0.07,
        },
        "narrative": build_narrative(),
        "delta_vs_market": 0.01,
        "delta_vs_yesterday": 0.0,
    }
    fields.update(overrides)
    return ForecastSubmission(**fields)
