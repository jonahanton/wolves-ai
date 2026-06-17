"""The post-acceptance revision loop is bounded and self-healing: it re-opens
at most graph_max_revisions times, clears the auto-submit state when it does so,
and republishes the prior accepted submission when a revision never re-accepts.
The published surface is stubbed; the contract under test is the loop control,
not the simulation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph import runner as runner_module
from wolves.graph.blackboard import Blackboard
from wolves.graph.runner import _should_continue_after_acceptance


@dataclass
class _FakeSurface:
    published_titles: dict[str, float]


@pytest.fixture
def deps_with_premortem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_max_revisions=1)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.artifacts = build_run_store(tmp_path)
    deps.artifacts.add(kind="critique", created_by="critic-1", summary="pre-mortem", payload={"challenges": ["x"]})
    monkeypatch.setattr(
        runner_module, "publish_surface", lambda *a, **k: _FakeSurface(published_titles={"england": 0.09})
    )
    return deps


def _board(deps) -> Blackboard:
    return Blackboard(artifacts=deps.artifacts, ledger=deps.ledger, runtime=deps.runtime)


def test_reopen_once_then_stop_when_budget_spent(deps_with_premortem):
    deps = deps_with_premortem
    board = _board(deps)
    accepted = build_submission()
    deps.submission.accepted = accepted
    deps.submission.checked_clean = accepted
    deps.submission.escalation_fired = True

    reopen, _ = _should_continue_after_acceptance(deps, board)
    assert reopen is True
    assert deps.submission.revisions_used == 1
    assert deps.submission.accepted is None
    assert deps.submission.checked_clean is None
    assert deps.submission.escalation_fired is False
    assert deps.submission.last_accepted is accepted
    assert deps.submission.counterfactual is accepted

    # A revision re-accepts; the budget is now spent, so the loop must not reopen.
    deps.submission.accepted = build_submission(artifact_id="mixture-002")
    reopen, reason = _should_continue_after_acceptance(deps, board)
    assert reopen is False
    assert "budget spent" in reason


def test_no_reopen_without_a_premortem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_max_revisions=1)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.artifacts = build_run_store(tmp_path)
    monkeypatch.setattr(runner_module, "publish_surface", lambda *a, **k: _FakeSurface(published_titles={}))
    deps.submission.accepted = build_submission()

    reopen, reason = _should_continue_after_acceptance(deps, _board(deps))
    assert reopen is False
    assert "pre-mortem" in reason


def test_disabled_loop_never_reopens(deps_with_premortem):
    deps = deps_with_premortem
    deps.settings.graph_max_revisions = 0
    deps.submission.accepted = build_submission()

    reopen, reason = _should_continue_after_acceptance(deps, _board(deps))
    assert reopen is False
    assert "disabled" in reason
