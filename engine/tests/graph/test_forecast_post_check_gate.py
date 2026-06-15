from __future__ import annotations

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.graph.agents import _forecast_post_check_refusal


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
