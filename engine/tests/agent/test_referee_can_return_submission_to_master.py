from __future__ import annotations

import json

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.tools.submission.referee import _referee_context
from wolves.agent.tools.submission.submit_forecast import _submit_forecast
from wolves.agent.validator import ValidationReport
from wolves.graph.agents import _forecast_post_check_refusal
from wolves.graph.fakes import scripted_output_model
from wolves.graph.observed_model import ObservedModel


def _referee_model(deps, outputs, *, captured_prompts=None):
    return ObservedModel(
        scripted_output_model(outputs, captured_prompts=captured_prompts),
        runtime=deps.runtime,
        actor="referee",
    )


def _seed_clean_submission_deps(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.settings.graph_referee_enabled = True
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
    deps.ledger.append(
        claim="England keeper trained",
        source_url="https://www.thefa.com/news",
        status="confirmed",
        mechanism="availability",
        team_id="england",
    )
    return deps


def _clean_submission():
    return build_submission(
        scenario_weights=[{"name": "baseline", "weight": 1.0, "rationale": "Baseline world remains live."}]
    )


async def test_referee_master_issue_blocks_once_and_writes_critique(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [
            {
                "approved": False,
                "summary": "France market premium was asserted but never audited.",
                "issues": [
                    {
                        "severity": "major",
                        "owner": "master",
                        "threshold": "large market disagreement without a quant audit",
                        "message": "The submission should not publish before the France gap is tested.",
                        "suggested_next_step": "Open a quant node to audit the France market gap.",
                    }
                ],
                "suggested_master_brief": "Audit the France market gap before final submission.",
            },
        ],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_replan_required"
    assert deps.submission.accepted is None
    assert deps.submission.referee_interventions == 1
    assert deps.submission.referee_replan_required is True
    assert deps.artifacts is not None
    critiques = [record for record in deps.artifacts.all() if record.kind == "critique"]
    assert len(critiques) == 1
    assert deps.artifacts.get(critiques[0].id).payload["suggested_master_brief"].startswith("Audit the France")
    deps.runtime.shutdown()


async def test_referee_approval_allows_clean_submission(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [{"approved": True, "summary": "Ready to publish.", "issues": [], "suggested_master_brief": ""}],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_retries_an_incomplete_report(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [
            {"approved": True, "summary": "Missing required fields."},
            {"approved": True, "summary": "Ready to publish.", "issues": [], "suggested_master_brief": ""},
        ],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_blocking_issue_overrides_approved_flag(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [
            {
                "approved": True,
                "summary": "Contradictory report with a blocker.",
                "issues": [
                    {
                        "severity": "major",
                        "owner": "forecast",
                        "threshold": "public copy contradiction",
                        "message": "The headline contradicts the published preview.",
                        "suggested_next_step": "Rewrite the headline from the preview.",
                    }
                ],
                "suggested_master_brief": "",
            },
        ],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_revision_required"
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_referee_minor_issue_does_not_block_publication(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [
            {
                "approved": False,
                "summary": "One caution, not a blocker.",
                "issues": [
                    {
                        "severity": "minor",
                        "owner": "forecast",
                        "threshold": "copy could be clearer",
                        "message": "The market explanation could be clearer.",
                        "suggested_next_step": "Consider tightening tomorrow.",
                    }
                ],
                "suggested_master_brief": "",
            },
        ],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert result.payload["accepted"] is True
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_disapproval_without_blocking_issue_publishes_clean_submission(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(
        deps,
        [{"approved": False, "summary": "Not ready.", "issues": [], "suggested_master_brief": ""}],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert result.payload["accepted"] is True
    assert deps.submission.publication_blocked is False
    assert deps.submission.referee_replan_required is False
    assert deps.submission.referee_interventions == 0
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_unavailable_publishes_clean_submission(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = _referee_model(deps, [])

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert result.payload["accepted"] is True
    assert result.payload["referee"]["bypassed"] is True
    assert deps.submission.publication_blocked is False
    assert deps.submission.referee_replan_required is False
    assert deps.submission.referee_interventions == 0
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_missing_referee_client_publishes_clean_submission(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_model = None

    result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert result.payload["accepted"] is True
    assert result.payload["referee"]["bypassed"] is True
    assert deps.submission.publication_blocked is False
    assert deps.submission.referee_replan_required is False
    assert deps.submission.referee_interventions == 0
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_intervention_cap_publishes_clean_submission(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.submission.referee_interventions = deps.settings.graph_referee_max_interventions
    deps.referee_model = _referee_model(
        deps,
        [
            {
                "approved": False,
                "summary": "Still blocked.",
                "issues": [
                    {
                        "severity": "major",
                        "owner": "master",
                        "threshold": "missing quant audit",
                        "message": "The market gap still has no quant audit.",
                        "suggested_next_step": "Stop publication.",
                    }
                ],
                "suggested_master_brief": "Audit the market gap.",
            },
        ],
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert result.payload["accepted"] is True
    assert result.payload["referee"]["bypassed"] is True
    assert deps.submission.publication_blocked is False
    assert deps.submission.referee_replan_required is False
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_context_includes_cited_ledger_rows(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    assert deps.artifacts is not None
    deps.artifacts.add(
        kind="evidence",
        created_by="research-1",
        summary="research scan",
        payload={
            "summary": "England availability checked.",
            "signals": ["Saka trained"],
            "candidate_branches": [{"branch_id": "england-availability"}],
        },
    )
    deps.artifacts.add(
        kind="retrieval",
        created_by="research-1",
        summary="ranked sources",
        payload={
            "sub_question": "England availability",
            "rankings": [{"url": "https://www.thefa.com/news", "score": 0.9, "reason": "official"}],
        },
    )
    deps.artifacts.add(
        kind="quant",
        created_by="quant-1",
        summary="market gap audit",
        payload={"summary": "France gap priced.", "findings": ["market premium tested"]},
    )
    captured_prompts: list[str] = []
    deps.referee_model = _referee_model(
        deps,
        [{"approved": True, "summary": "Ready.", "issues": [], "suggested_master_brief": ""}],
        captured_prompts=captured_prompts,
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert "led-0001" in captured_prompts[0]
    assert "England keeper trained" in captured_prompts[0]
    assert "https://www.thefa.com/news" in captured_prompts[0]
    context = json.loads(captured_prompts[0])
    assert context["published_preview"]
    assert context["artifact"]["weights"] == {"baseline": 1.0}
    assert "research_artifacts" not in context
    assert "retrieval_artifacts" not in context
    assert "quant_artifacts" not in context
    assert "branch_audit" in context
    assert "factor_audit" in context
    assert "world_metadata" in context
    deps.runtime.shutdown()


async def test_referee_context_names_visible_camp_surface(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.settings.graph_referee_enabled = True
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(
        kind="mixture",
        created_by="quant-1",
        summary="two worlds, one visible camp",
        payload={
            "weights": {"model_base": 0.5, "market_base": 0.5},
            "worlds": {"model_base": {"perturbations": []}, "market_base": {"perturbations": []}},
            "mixture": {"england": 0.08, "rest": 0.92},
        },
    )
    submission = build_submission(
        scenario_weights=[
            {"name": "model_base", "weight": 0.5, "camp": "baseline", "rationale": "Model base."},
            {"name": "market_base", "weight": 0.5, "camp": "baseline", "rationale": "Market base."},
        ],
        camps=[{"key": "baseline", "label": "Baseline blend", "summary": "Model and market agree.", "order": 1}],
    )

    context = _referee_context(submission, deps, ValidationReport(ok=True))
    visible = context["public_surface"]["visible_distribution"]
    assert visible["bucket_type"] == "camps"
    assert visible["bucket_count"] == 1
    assert visible["raw_world_count"] == 2
    assert visible["buckets"][0]["weight"] == 1.0
    deps.runtime.shutdown()


def test_referee_replan_latch_refuses_more_forecast_tools(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.referee_replan_required = True

    refusal = _forecast_post_check_refusal("check_forecast", deps)

    assert refusal is not None
    assert not refusal.ok
    assert refusal.error is not None
    assert refusal.error.type == "referee_replan_required"
    deps.runtime.shutdown()
