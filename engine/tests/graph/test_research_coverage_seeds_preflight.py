from __future__ import annotations

from pathlib import Path

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.config import Settings
from wolves.graph.contracts import ForecastOutput, GraphPatch, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.research_coverage import (
    ResearchCoverageHint,
    ResearchCoverageSignals,
    research_coverage_brief,
    should_seed_research,
)
from wolves.graph.runner import GraphModels, run_graph
from wolves.snapshot import FocusTeamBlock, RunMeta, Snapshot, TeamInfo


def _previous_snapshot(run_id: str) -> Snapshot:
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at="2026-06-13T14:56:13+00:00",
            as_of="2026-06-13",
            n_sims=100,
            engine_version="0",
            kind="agent",
        ),
        focus=FocusTeamBlock(team_id="england", group="L", finish_probs={}, reach_probs={}, paths=[]),
        slots=[],
        teams=[TeamInfo(team_id="england", name="England", group="L", elo=2000, champion_prob=0.08)],
    )


async def test_stale_previous_run_seeds_coverage_without_spending_master_wave(tmp_path: Path):
    run_id = "agent-20260613-140248"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / f"{run_id}.json").write_text(_previous_snapshot(run_id).model_dump_json())
    deps = build_graph_deps(tmp_path)
    deps.as_of = "2026-06-15"
    deps.submission.accepted = build_submission()
    models = GraphModels(
        master=scripted_model([GraphPatch(stop=True, reason="coverage enough")], model_name="master"),
        nodes={
            "research": scripted_model([], model_name="unused"),
            "quant": scripted_model(
                [ResearchOutput(summary="coverage checked", signals=["no material public development found"])],
                model_name="standard-worker",
            ),
            "forecast": scripted_model([ForecastOutput(summary="no submission")], model_name="forecast"),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-15", models=models)
    deps.runtime.shutdown()

    assert result.waves == 0
    assert deps.artifacts is not None
    assert any(record.created_by == "coverage-research" for record in deps.artifacts.all())
    [receipt] = [record for record in deps.artifacts.all() if record.kind == "report"]
    assert receipt.summary.startswith("research coverage standard_suggested")


def test_thin_previous_research_seeds_preflight():
    hint = ResearchCoverageHint(
        level="light_suggested",
        reasons=["previous run had very thin web research"],
        signals=ResearchCoverageSignals(
            previous_run_id="agent-20260613-140248",
            previous_web_searches=0,
            previous_retrieval_artifacts=0,
        ),
    )

    assert should_seed_research(hint)


def test_scratch_run_without_previous_can_seed_preflight():
    hint = ResearchCoverageHint(
        level="standard_suggested",
        reasons=["no previous agent forecast is available"],
        signals=ResearchCoverageSignals(scratch_run=True),
    )

    assert should_seed_research(hint)


def test_coverage_brief_keeps_search_broad_bounded_and_provider_flexible():
    hint = ResearchCoverageHint(
        level="standard_suggested",
        reasons=["scratch run"],
        lanes=["open-ended material developments"],
        signals=ResearchCoverageSignals(scratch_run=True),
    )

    brief = research_coverage_brief(hint, as_of="2026-06-15")
    lower = brief.lower()

    assert "private ids" in lower
    assert "exa" in lower and "brave" in lower
    assert "stale or generic" in lower
    assert "at most four" in lower
    assert "open-ended search" in lower


def test_open_scenarios_alone_do_not_seed_research():
    hint = ResearchCoverageHint(
        level="light_suggested",
        reasons=["1 open scenario(s) need lifecycle audit"],
        signals=ResearchCoverageSignals(
            previous_run_id="agent-20260613-140248",
            open_scenarios=1,
        ),
    )

    assert not should_seed_research(hint)


async def test_coverage_preflight_respects_zero_wave_cap(tmp_path: Path):
    run_id = "agent-20260613-140248"
    snapshot_dir = tmp_path / "snapshots" / "2026" / "06" / "13"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / f"{run_id}.json").write_text(_previous_snapshot(run_id).model_dump_json())
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_max_waves=0)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.as_of = "2026-06-15"
    deps.submission.accepted = build_submission()
    models = GraphModels(
        master=scripted_model([], model_name="unused"),
        nodes={
            "research": scripted_model([], model_name="unused"),
            "quant": scripted_model([], model_name="unused"),
            "forecast": scripted_model([], model_name="unused"),
            "critic": scripted_model([], model_name="unused"),
        },
    )

    result = await run_graph(deps, as_of="2026-06-15", models=models)
    deps.runtime.shutdown()

    assert result.waves == 0
    assert deps.artifacts is not None
    assert not any(record.created_by == "coverage-research" for record in deps.artifacts.all())
