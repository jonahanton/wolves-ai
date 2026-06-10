from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult
from wolves.quant.context import build_sandbox_context

_RESULT_CAP_CHARS = 8_000
_STDOUT_CAP_CHARS = 2_000


class RunPythonArgs(BaseModel):
    code: str


async def _run_python(args: RunPythonArgs, deps: AgentDeps) -> ToolResult[Any]:
    deps.python_calls += 1
    workspace = deps.quant.workspace(deps.actor)
    deps.quant.write_context(workspace, build_sandbox_context(deps))
    script = workspace.next_analysis_name()
    deps.quant.write_analysis(actor=deps.actor, workspace=workspace, code=args.code, filename=script)
    result = await deps.quant.execute(actor=deps.actor, workspace=workspace, script=script)
    _register_mixtures(deps, workspace_dir=workspace.dir.name, files=[o.filename for o in result.output_files])
    result_text = json.dumps(result.result_value, ensure_ascii=False, default=str)
    return ToolResult(
        ok=result.ok,
        payload={
            "result": result.result_value if len(result_text) <= _RESULT_CAP_CHARS else result_text[:_RESULT_CAP_CHARS],
            "stdout": result.stdout[:_STDOUT_CAP_CHARS],
            "stderr": result.stderr[-_STDOUT_CAP_CHARS:],
            "script": script,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "usage": result.usage,
            "output_files": [o.filename for o in result.output_files],
            **({"error": result.error} if result.error else {}),
        },
    )


def _register_mixtures(deps: AgentDeps, *, workspace_dir: str, files: list[str]) -> None:
    """Mixture artifacts computed in the sandbox become run artifacts the
    forecast node can cite and submit by reference."""
    store = deps.artifacts
    if store is None:
        return
    registered = {r.summary for r in store.all() if r.kind == "mixture"}
    for filename in files:
        if not (filename.startswith("mixture") and filename.endswith(".json")):
            continue
        marker = f"{workspace_dir}/{filename}"
        if marker in registered:
            continue
        workspace = deps.quant.workspace(deps.actor)
        payload = json.loads((workspace.outputs / filename).read_text(encoding="utf-8"))
        store.add(
            kind="mixture",
            created_by=deps.actor,
            summary=marker,
            payload=payload,
            workspace_prefix=f"runs/{store.run_id}/workspace/quant/{workspace_dir}",
        )


SPEC = ToolSpec(
    name="run_python",
    description=(
        "Run Python in your persistent analysis workspace (no network; numbered scripts share one "
        "directory per node, so earlier variables are gone but files under inputs/ and outputs/ "
        "persist between calls). Preloaded names: wq (the workbench: wq.query/load_* over the "
        "research data, wq.simulate/baseline/impact with common random numbers, wq.match_probs "
        "(pass match=<id> to bind match-keyed perturbations), wq.scenario_mixture for factor "
        "lattices, wq.posterior_draws, wq.artifact/artifact_path to open prior nodes' work), "
        "pd (pandas) and np (numpy). End every script by assigning the finding to `result` "
        "(JSON-safe; a bare expression or print() does not count). Deltas from wq.impact carry a "
        "paired-seed noise floor: treat anything below it as simulation noise. This tool is free: "
        "it never consumes your tool budget, so computing beats guessing."
    ),
    args_model=RunPythonArgs,
    fn=_run_python,
)
