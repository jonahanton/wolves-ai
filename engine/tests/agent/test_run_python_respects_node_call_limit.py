from __future__ import annotations

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.workbench.run_python import RunPythonArgs, _run_python
from wolves.config import Settings


async def test_run_python_refuses_after_node_limit(tmp_path):
    settings = Settings(_env_file=None, runs_root=tmp_path, storage_mode="local", graph_quant_python_call_limit=1)
    deps = build_graph_deps(tmp_path, settings=settings)
    deps.actor = "quant-gap"
    deps.python_calls = 1

    result = await _run_python(RunPythonArgs(code="result = {'ok': True}"), deps)

    assert not result.ok
    assert result.error is not None
    assert result.error.type == "python_budget_exhausted"
    assert result.payload == {"limit": 1, "used": 1}
    assert not list((deps.runtime.paths.workspace / "quant").rglob("analysis_*.py"))
    deps.runtime.shutdown()
