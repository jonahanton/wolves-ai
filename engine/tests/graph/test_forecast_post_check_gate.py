from __future__ import annotations

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.graph.agents import _forecast_post_check_refusal
from wolves.graph.runner import _reset_forecast_copy_state, _submit_clean_preview
from wolves.toolkit.result import ToolResult


def test_clean_forecast_preview_blocks_more_forecast_tooling(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.checked_clean = build_submission()

    refusal = _forecast_post_check_refusal("team_dossier", deps)

    assert refusal is not None
    assert not refusal.ok
    assert refusal.error is not None
    assert refusal.error.type == "clean_forecast_already_checked"


def test_clean_forecast_preview_still_allows_journal_and_submit(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.checked_clean = build_submission()

    assert _forecast_post_check_refusal("write_journal", deps) is None
    assert _forecast_post_check_refusal("submit_forecast", deps) is None


def test_copy_repair_blocks_more_forecast_tooling(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.copy_repair_required = True

    refusal = _forecast_post_check_refusal("team_path_tree", deps)

    assert refusal is not None
    assert not refusal.ok
    assert refusal.error is not None
    assert refusal.error.type == "copy_repair_required"


def test_copy_repair_allows_recheck_and_resubmit(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.copy_repair_required = True

    assert _forecast_post_check_refusal("check_forecast", deps) is None
    assert _forecast_post_check_refusal("submit_forecast", deps) is None


def test_referee_copy_repair_can_resubmit_while_publication_is_blocked(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.copy_repair_required = True
    deps.submission.publication_blocked = True

    assert _forecast_post_check_refusal("check_forecast", deps) is None
    assert _forecast_post_check_refusal("submit_forecast", deps) is None
    refusal = _forecast_post_check_refusal("team_path_tree", deps)
    assert refusal is not None
    assert refusal.error is not None
    assert refusal.error.type == "copy_repair_required"


def test_new_forecast_attempt_resets_copy_repair_loop(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.submission.copy_repair_required = True
    deps.submission.publication_blocked = True
    deps.submission.copy_issue_signature = ("headline_too_long:old",)
    deps.submission.copy_issue_repeats = 3
    deps.submission.copy_repair_blocked = True

    _reset_forecast_copy_state(deps)

    assert _forecast_post_check_refusal("read_artifact", deps) is None
    assert deps.submission.copy_issue_signature is None
    assert deps.submission.copy_issue_repeats == 0
    assert deps.submission.publication_blocked is False


async def test_runner_auto_submits_clean_preview(tmp_path, monkeypatch):
    deps = build_graph_deps(tmp_path)
    checked = build_submission()
    deps.submission.checked_clean = checked

    async def fake_submit(args, tool_deps):
        deps.submission.accepted = args
        return ToolResult(payload={"accepted": True})

    monkeypatch.setattr("wolves.graph.runner._submit_forecast", fake_submit)

    await _submit_clean_preview(deps)
    deps.runtime.shutdown()

    assert deps.submission.accepted == checked
