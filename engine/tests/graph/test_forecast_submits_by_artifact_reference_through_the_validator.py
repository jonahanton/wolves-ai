"""End-to-end offline proof of the graph: a scripted master plans a research
wave then a forecast node; the validator rejects an invalid submission inside
the node's own run, the valid resubmission by artifact reference passes, and
the run state (ledger, lessons, journal, events) all lands."""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.graph.contracts import ForecastOutput, GraphPatch, LedgerEvidence, NodePatch, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import EventLog

SCENARIO_WEIGHTS = [
    {"name": "plays", "weight": 0.6, "rationale": "Keeper plays after training in full."},
    {"name": "out", "weight": 0.4, "rationale": "Keeper absence still carries some squad risk."},
]

INVALID = build_submission(
    artifact_id="mixture-999",
    narrative=build_submission().narrative.model_copy(
        update={"focus_story": "England cruise — nothing to worry about.", "slot_rationales": {"73": "only one"}}
    ),
    scenario_weights=SCENARIO_WEIGHTS,
)
VALID = build_submission(
    market_justification="Confirmed keeper news the books have not priced.",
    scenario_weights=SCENARIO_WEIGHTS,
)

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
        [("write_journal", {"text": "Checked keeper news.", "lessons": "Anchor on odds before news."})],
        [("submit_forecast", INVALID.model_dump())],
        [("submit_forecast", VALID.model_dump())],
        ForecastOutput(summary="Submitted by artifact reference after fixing the rationales."),
    ],
    model_name="forecast",
)


def _forecast_wave(prompt: str) -> GraphPatch:
    artifact_ids = sorted(set(re.findall(r"(?:evidence|mixture)-\d{3}", prompt)))
    return GraphPatch(
        ops=[
            NodePatch(
                node_id="forecast",
                kind="forecast",
                objective="Submit today's forecast",
                brief="Weigh the keeper evidence and submit.",
                input_artifact_ids=artifact_ids,
            )
        ]
    )


async def test_full_graph_run(tmp_path: Path):
    deps = build_graph_deps(tmp_path, run_id="e2e-run")
    deps.artifacts = build_run_store(tmp_path, run_id="e2e-run")
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-saka",
        summary="saka mixture",
        payload={
            "weights": {"plays": 0.6, "out": 0.4},
            "worlds": {
                "plays": {"perturbations": []},
                "out": {"perturbations": [{"team": "england", "delta": -0.1, "reason": "saka out"}]},
            },
            "mixture": {"england": 0.066, "rest": 0.934},
        },
    )
    master = scripted_model(
        [
            GraphPatch(ops=[NodePatch(node_id="research-keeper", kind="research", objective="keeper", brief="...")]),
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
    assert result.submission.artifact_id == "mixture-001"

    assert deps.ledger.get("led-0001") is not None
    assert "Anchor on odds" in deps.settings.lessons_path.read_text()
    assert (tmp_path / "runs" / "e2e-run" / "journal.md").exists()

    events = EventLog.read(deps.runtime.paths.events)
    kinds = {e.kind for e in events}
    assert {"web_search", "ledger", "validation", "journal"} <= kinds
    summaries = [e.summary for e in events if e.kind == "validation"]
    assert any("rejected" in s for s in summaries)
    assert any("accepted" in s for s in summaries)
