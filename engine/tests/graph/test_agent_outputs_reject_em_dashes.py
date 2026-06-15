from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry

from wolves.graph.agents import _em_dash_paths, _reject_em_dashes
from wolves.graph.contracts import GraphPatch, NodePatch, ResearchOutput


def test_worker_output_reports_em_dash_paths():
    dash = chr(8212)
    output = ResearchOutput(summary=f"Prices moved{dash}slightly")

    assert _em_dash_paths(output) == ["$.summary"]
    issues = _reject_em_dashes(output)
    assert issues
    with pytest.raises(ModelRetry):
        raise ModelRetry(" ".join(issues))


def test_master_patch_reports_nested_em_dash_paths():
    dash = chr(8212)
    patch = GraphPatch(
        reason="Open one wave",
        ops=[
            NodePatch(
                node_id="research-tape",
                kind="research",
                objective="Check tape",
                brief=f"Confirm results{dash}no pricing.",
            )
        ],
    )

    assert _em_dash_paths(patch) == ["$.ops[0].brief"]
