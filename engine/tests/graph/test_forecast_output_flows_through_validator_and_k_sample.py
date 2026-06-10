"""End-to-end offline proof of the graph: a scripted master plans a research
wave then a forecast node; the validator rejects an invalid submission inside
the node's own run, the tripwire injects an explain-or-revise turn, the valid
resubmission passes, and the K-sample median plus event log all work."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.graph.contracts import Brief, ForecastOutput, LedgerEvidence, ResearchOutput, WavePlan
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import EventLog

INVALID = build_submission(
    narrative=build_submission().narrative.model_copy(
        update={"england_story": "England cruise — nothing to worry about.", "slot_rationales": {"73": "only one"}}
    )
)
VALID = build_submission(delta_vs_market=0.12, market_justification="Confirmed keeper news the books have not priced.")

K_SAMPLES = [
    {"rating_overrides": [{"team_id": "england", "delta_elo": 21.0, "cause": "keeper", "ledger_ids": ["led-0001"]}]},
    {"rating_overrides": [{"team_id": "england", "delta_elo": 9.0, "cause": "keeper", "ledger_ids": ["led-0001"]}]},
]

RESEARCH = scripted_model(
    [
        [("web_search", {"query": "England squad news Croatia", "freshness": "pd"})],
        ResearchOutput(
            summary="Keeper confirmed fit by the FA.",
            evidence=[
                LedgerEvidence(
                    claim="First-choice keeper confirmed fit by the FA",
                    source_url="https://www.reuters.com/world/example-article-2026",
                    quote="trained in full",
                    status="confirmed",
                    mechanism="keeper returns to the XI",
                    proposed_delta=15.0,
                    team_id="england",
                )
            ],
        ),
    ],
    model_name="research",
)

FORECAST = scripted_model(
    [
        [("ledger_query", {"team_id": "england"})],
        [("run_simulation", {"rating_overrides": {"england": 15.0}, "n_sims": 300, "seed": 1})],
        [("write_journal", {"text": "Checked keeper news, ran sim.", "lessons": "Anchor on odds before news."})],
        [("submit_forecast", INVALID.model_dump())],
        [("submit_forecast", VALID.model_dump())],
        [("submit_forecast", VALID.model_dump())],
        ForecastOutput(summary="Submitted after fixing the rationales and answering the tripwire."),
    ],
    model_name="forecast",
)


def _forecast_wave(prompt: str) -> WavePlan:
    artifact_ids = sorted(set(re.findall(r"evidence-[0-9a-f]{8}", prompt)))
    return WavePlan(
        briefs=[
            Brief(
                node_id="forecast",
                kind="forecast",
                objective="Submit today's forecast",
                brief="Weigh the keeper evidence and submit.",
                input_artifact_ids=artifact_ids,
            )
        ]
    )


async def test_full_graph_run(tmp_path: Path):
    deps = build_graph_deps(tmp_path, structured=list(K_SAMPLES), run_id="e2e-run")
    master = scripted_model(
        [
            WavePlan(briefs=[Brief(node_id="research-keeper", kind="research", objective="keeper", brief="...")]),
            _forecast_wave,
        ],
        model_name="master",
    )
    models = GraphModels(
        master=master,
        nodes={
            "research": RESEARCH,
            "quant": scripted_model([], model_name="unused"),
            "forecast": FORECAST,
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    deps.runtime.shutdown()

    assert result.submission is not None
    assert not result.budget_exhausted
    assert result.validation_failures == 1
    assert result.waves == 2

    by_team = {o.team_id: o.delta_elo for o in result.submission.rating_overrides}
    assert by_team == {"england": 15.0}
    assert result.disagreement is not None
    assert result.disagreement.k == 3
    assert result.disagreement.max_spread == pytest.approx(12.0)

    assert deps.ledger.get("led-0001") is not None
    assert "Anchor on odds" in deps.settings.lessons_path.read_text()
    assert (tmp_path / "e2e-run" / "journal.md").exists()

    events = EventLog.read(deps.runtime.paths.events)
    kinds = {e.kind for e in events}
    assert {"web_search", "quant", "ledger", "validation", "tripwire", "journal"} <= kinds
    summaries = [e.summary for e in events if e.kind == "validation"]
    assert any("rejected" in s for s in summaries)
    assert any("accepted" in s for s in summaries)
