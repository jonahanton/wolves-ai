from __future__ import annotations

import json

from tests.graph.conftest import build_graph_deps, build_run_store
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


async def test_run_python_returns_registered_mixture_artifact_ids(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
    "factor_audit": {"verdict": "quiet day", "checks": []},
}
open("outputs/submit_ready.json", "w", encoding="utf-8").write(json.dumps(payload))
result = {"built": True}
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert result.ok
    assert result.payload["registered_artifact_ids"] == ["mixture-001"]
    assert deps.artifacts.get("mixture-001").payload["weights"] == {"model": 1.0}
    assert deps.artifacts.get("mixture-001").payload["factor_audit"]["verdict"] == "quiet day"


async def test_run_python_does_not_register_mixture_without_worlds(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
}
open("outputs/not_publishable.json", "w", encoding="utf-8").write(json.dumps(payload))
result = {"built": True}
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert result.ok
    assert result.payload["registered_artifact_ids"] == []
    assert deps.artifacts.get("mixture-001") is None


async def test_run_python_registers_audit_mixture_rewrite(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
    "artifact_file": "outputs/submit_ready.json",
}
open("outputs/submit_ready.json", "w", encoding="utf-8").write(json.dumps(payload))
audit = wq.factor_audit(checks=[], verdict="retrofitted audit")
result = wq.audit_mixture(payload, audit)
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert result.ok
    assert result.payload["registered_artifact_ids"] == ["mixture-001"]
    assert deps.artifacts.get("mixture-001").payload["factor_audit"]["verdict"] == "retrofitted audit"


async def test_run_python_amends_registered_mixture_when_output_file_changes(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        first = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
    "artifact_file": "outputs/submit_ready.json",
}
open("outputs/submit_ready.json", "w", encoding="utf-8").write(json.dumps(payload))
result = {"built": True}
"""
            ),
            deps,
        )
        second = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = json.load(open("outputs/submit_ready.json", encoding="utf-8"))
audit = wq.factor_audit(checks=[], verdict="second script audit")
result = wq.audit_mixture(payload, audit)
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert first.ok and first.payload["registered_artifact_ids"] == ["mixture-001"]
    assert second.ok and second.payload["registered_artifact_ids"] == ["mixture-001"]
    assert deps.artifacts.get("mixture-001").payload["factor_audit"]["verdict"] == "second script audit"


async def test_run_python_does_not_register_mixture_from_failed_script(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
}
open("outputs/failed.json", "w", encoding="utf-8").write(json.dumps(payload))
raise RuntimeError("after writing")
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert not result.ok
    assert result.payload["registered_artifact_ids"] == []
    assert deps.artifacts.get("mixture-001") is None


async def test_run_python_registers_mixture_when_result_assignment_is_missing(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
}
open("outputs/submit_ready.json", "w", encoding="utf-8").write(json.dumps(payload))
print("mixture written")
"""
            ),
            deps,
        )

    deps.runtime.shutdown()
    assert not result.ok
    assert result.payload["registered_artifact_ids"] == ["mixture-001"]
    assert result.payload["recovery_hint"] == "valid mixture outputs were registered despite the missing result"
    assert deps.artifacts.get("mixture-001").payload["weights"] == {"model": 1.0}


async def test_run_python_does_not_register_stale_failed_output_after_success(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        failed = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
}
open("outputs/stale.json", "w", encoding="utf-8").write(json.dumps(payload))
raise RuntimeError("after writing")
"""
            ),
            deps,
        )
        success = await _run_python(RunPythonArgs(code="result = {'ok': True}"), deps)

    deps.runtime.shutdown()
    assert not failed.ok
    assert success.ok
    assert success.payload["output_files"] == []
    assert success.payload["registered_artifact_ids"] == []
    assert deps.artifacts.get("mixture-001") is None


async def test_run_python_refreshes_context_for_same_node_artifacts(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.artifacts = build_run_store(tmp_path, run_id=deps.runtime.run_id)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        first = await _run_python(
            RunPythonArgs(
                code="""
import json

payload = {
    "weights": {"model": 1.0},
    "worlds": {"model": {"perturbations": []}},
    "mixture": {"england": 0.08},
    "conditionals": {"model": {"england": 0.08}},
}
open("outputs/submit_ready.json", "w", encoding="utf-8").write(json.dumps(payload))
result = {"built": True}
"""
            ),
            deps,
        )
        second = await _run_python(RunPythonArgs(code="result = wq.artifact('mixture-001')['weights']"), deps)

    deps.runtime.shutdown()
    assert first.ok
    assert second.ok
    assert second.payload["result"] == {"model": 1.0}


async def test_run_python_failure_events_include_stderr_tail(tmp_path):
    deps = build_graph_deps(tmp_path)
    deps.actor = "quant-build"

    with deps.runtime.run_trace(title="run_python test"):
        result = await _run_python(RunPythonArgs(code="result = 1 / 0"), deps)

    deps.runtime.shutdown()
    assert not result.ok
    events = [
        json.loads(line)
        for line in deps.runtime.paths.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    [quant_event] = [event for event in events if event["kind"] == "quant_exec"]
    assert "ZeroDivisionError" in quant_event["payload"]["stderr_tail"]
