from __future__ import annotations

from pathlib import Path

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph.contracts import ForecastOutput, GraphPatch, NodePatch, QuantOutput, ResearchOutput
from wolves.graph.fakes import scripted_model, scripted_output_model
from wolves.graph.observed_model import ObservedModel
from wolves.graph.runner import GraphModels, run_graph
from wolves.observability import EventLog


async def test_demand_submit_runs_after_hard_retries_exhausted(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local")
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.submission.validation_failures = settings.agent_submit_retries + 1

    demanded: list[str] = []

    def forced_submit(prompt: str) -> ForecastOutput:
        demanded.append(prompt)
        return ForecastOutput(summary="forced submit")

    models = GraphModels(
        master=scripted_model(
            [GraphPatch(ops=[NodePatch(node_id="research-1", kind="research", objective="r", brief="r")])]
        ),
        nodes={
            "research": scripted_model([ResearchOutput(summary="wave one")], model_name="research"),
            "quant": scripted_model([], model_name="unused"),
            "forecast": scripted_model([forced_submit]),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    deps.runtime.shutdown()

    assert demanded, "exhausted hard retries must not skip the final demand-submit"
    assert result.validation_failures == settings.agent_submit_retries + 1


async def test_demand_submit_does_not_bypass_unadjudicated_branch(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path)
    entry = deps.ledger.append(
        claim="France market is materially higher than the model",
        source_url="internal://get_odds",
        status="confirmed",
        mechanism="market disagreement",
        proposed_delta=0.05,
        team_id="france",
    )
    deps.artifacts.add(
        kind="evidence",
        created_by="research-news",
        summary="france market branch",
        payload={
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "The market may know something material about France.",
                    "support": "The market is materially higher than the model.",
                    "collapse_condition": "Collapse if the gap sits inside the uncertainty floor.",
                    "source_ids": [entry.id],
                    "confidence": "medium",
                    "suggested_quant_question": "Price the France market premium.",
                }
            ]
        },
    )
    models = GraphModels(
        master=scripted_model([GraphPatch(stop=True, reason="done")], model_name="master"),
        nodes={
            "research": scripted_model([], model_name="unused"),
            "quant": scripted_model([], model_name="unused"),
            "forecast": scripted_model([ForecastOutput(summary="would demand submit")], model_name="forecast"),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    events = EventLog.read(deps.runtime.paths.events)
    deps.runtime.shutdown()

    assert result.submission is None
    assert not any(event.kind == "node" and event.actor == "runner-demand-submit" for event in events)


async def test_referee_replan_returns_to_master_before_terminal_path(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_referee_enabled=True)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="baseline",
        payload={
            "weights": {"baseline": 1.0},
            "worlds": {"baseline": {"perturbations": []}},
            "mixture": {"england": 0.08, "rest": 0.92},
        },
    )
    deps.referee_model = ObservedModel(
        scripted_output_model(
            [
                {
                    "approved": False,
                    "summary": "France market premium still needs a quant audit.",
                    "issues": [
                        {
                            "severity": "major",
                            "owner": "quant",
                            "threshold": "material branch unaudited",
                            "message": "The France branch should be priced or collapsed.",
                            "suggested_next_step": "Open a quant node for the France market branch.",
                        }
                    ],
                    "suggested_master_brief": "Open a quant node for the France market branch.",
                },
            ]
        ),
        runtime=deps.runtime,
        actor="referee",
    )
    submission = build_submission(
        evidence_ids=[], scenario_weights=[{"name": "baseline", "weight": 1.0, "rationale": "Baseline remains live."}]
    )
    models = GraphModels(
        master=scripted_model(
            [
                GraphPatch(
                    ops=[NodePatch(node_id="forecast-1", kind="forecast", objective="submit", brief="submit")],
                    stop=True,
                ),
                GraphPatch(ops=[NodePatch(node_id="quant-follow-up", kind="quant", objective="audit", brief="audit")]),
                GraphPatch(stop=True, reason="blocked"),
            ],
            model_name="master",
        ),
        nodes={
            "research": scripted_model([], model_name="unused"),
            "quant": scripted_model([QuantOutput(summary="quant follow-up ran")], model_name="quant"),
            "forecast": scripted_model(
                [[("submit_forecast", submission.model_dump())], ForecastOutput(summary="referee blocked")],
                model_name="forecast",
            ),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    events = EventLog.read(deps.runtime.paths.events)
    deps.runtime.shutdown()

    assert result.submission is None
    assert deps.submission.publication_blocked is True
    assert any(event.kind == "node" and event.actor == "quant-follow-up" for event in events)
    assert not any(event.kind == "node" and event.actor == "runner-demand-submit" for event in events)


async def test_referee_infrastructure_block_publishes_without_replan(tmp_path: Path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_referee_enabled=True)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="baseline",
        payload={
            "weights": {"baseline": 1.0},
            "worlds": {"baseline": {"perturbations": []}},
            "mixture": {"england": 0.08, "rest": 0.92},
        },
    )
    deps.referee_model = ObservedModel(scripted_output_model([]), runtime=deps.runtime, actor="referee")
    submission = build_submission(
        evidence_ids=[], scenario_weights=[{"name": "baseline", "weight": 1.0, "rationale": "Baseline remains live."}]
    )
    models = GraphModels(
        master=scripted_model(
            [
                GraphPatch(
                    ops=[NodePatch(node_id="forecast-1", kind="forecast", objective="submit", brief="submit")],
                    stop=False,
                ),
                GraphPatch(
                    ops=[NodePatch(node_id="quant-should-not-run", kind="quant", objective="audit", brief="audit")]
                ),
            ],
            model_name="master",
        ),
        nodes={
            "research": scripted_model([], model_name="unused"),
            "quant": scripted_model([QuantOutput(summary="quant should not run")], model_name="quant"),
            "forecast": scripted_model(
                [[("submit_forecast", submission.model_dump())], ForecastOutput(summary="referee unavailable")],
                model_name="forecast",
            ),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-10", models=models)
    events = EventLog.read(deps.runtime.paths.events)
    deps.runtime.shutdown()

    assert result.submission is not None
    assert deps.submission.publication_blocked is False
    assert deps.submission.referee_replan_required is False
    assert not any(event.kind == "node" and event.actor == "quant-should-not-run" for event in events)
    assert not any(event.kind == "node" and event.actor == "runner-demand-submit" for event in events)
