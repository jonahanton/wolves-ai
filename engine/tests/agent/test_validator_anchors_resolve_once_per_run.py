from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import build_submission
from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.submission import _validation


def test_baseline_and_market_anchors_compute_once_across_attempts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deps = build_graph_deps(tmp_path)
    calls: list[str] = []

    def baseline(_deps) -> dict[str, float]:
        calls.append("baseline")
        return {"england": 0.1}

    def market(_deps) -> None:
        calls.append("market")
        return None

    monkeypatch.setattr(_validation, "_baseline_titles", baseline)
    monkeypatch.setattr(_validation, "_market_titles", market)

    _validation.validation_report(build_submission(), deps)
    _validation.validation_report(build_submission(), deps)
    deps.runtime.shutdown()

    assert calls == ["baseline", "market"]
