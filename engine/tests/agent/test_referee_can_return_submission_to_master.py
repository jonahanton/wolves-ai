from __future__ import annotations

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.agent.fakes import ScriptedLLM
from wolves.agent.tools.submission.submit_forecast import _submit_forecast
from wolves.graph.agents import _forecast_post_check_refusal
from wolves.llm.observed import ObservedLLM


class CapturingScriptedLLM(ScriptedLLM):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_user = ""

    async def complete(self, **kwargs):
        self.last_user = kwargs["user"]
        return await super().complete(**kwargs)


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
    deps.referee_llm = ObservedLLM(
        ScriptedLLM(
            turns=[],
            structured=[
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
                }
            ],
        ),
        deps.runtime,
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
    deps.referee_llm = ObservedLLM(
        ScriptedLLM(
            turns=[],
            structured=[{"approved": True, "summary": "Ready to publish.", "issues": [], "suggested_master_brief": ""}],
        ),
        deps.runtime,
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert deps.submission.accepted is not None
    deps.runtime.shutdown()


async def test_referee_blocking_issue_overrides_approved_flag(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_llm = ObservedLLM(
        ScriptedLLM(
            turns=[],
            structured=[
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
                }
            ],
        ),
        deps.runtime,
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_revision_required"
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_referee_disapproval_without_issue_blocks(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_llm = ObservedLLM(
        ScriptedLLM(
            turns=[],
            structured=[{"approved": False, "summary": "Not ready.", "issues": [], "suggested_master_brief": ""}],
        ),
        deps.runtime,
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_replan_required"
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_referee_unavailable_blocks_publication(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_llm = ObservedLLM(ScriptedLLM(turns=[], structured=[]), deps.runtime)

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_replan_required"
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_missing_referee_client_blocks_when_enabled(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.referee_llm = None

    result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_replan_required"
    assert deps.submission.publication_blocked is True
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_referee_intervention_cap_does_not_publish_blocker(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    deps.submission.referee_interventions = deps.settings.graph_referee_max_interventions
    deps.referee_llm = ObservedLLM(
        ScriptedLLM(
            turns=[],
            structured=[
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
                }
            ],
        ),
        deps.runtime,
    )

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "referee_blocked"
    assert deps.submission.accepted is None
    deps.runtime.shutdown()


async def test_referee_context_includes_cited_ledger_rows(tmp_path):
    deps = _seed_clean_submission_deps(tmp_path)
    client = CapturingScriptedLLM(
        turns=[],
        structured=[{"approved": True, "summary": "Ready.", "issues": [], "suggested_master_brief": ""}],
    )
    deps.referee_llm = ObservedLLM(client, deps.runtime)

    with deps.runtime.run_trace():
        result = await _submit_forecast(_clean_submission(), deps)

    assert result.ok
    assert "led-0001" in client.last_user
    assert "England keeper trained" in client.last_user
    assert "https://www.thefa.com/news" in client.last_user
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
