from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolResult


class RunPythonArgs(BaseModel):
    code: str


async def _run_python(args: RunPythonArgs, deps: AgentDeps) -> ToolResult[Any]:
    deps.python_calls += 1
    workspace = deps.quant.workspace(f"{deps.actor}-py-{deps.python_calls}")
    deps.quant.write_analysis(actor=deps.actor, workspace=workspace, code=args.code)
    result = await deps.quant.execute(actor=deps.actor, workspace=workspace)
    return ToolResult(
        ok=result.ok,
        payload={
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "output_files": [o.filename for o in result.output_files],
        },
    )


SPEC = ToolSpec(
    name="run_python",
    description=(
        "Run a sandboxed Python script (no network, no subprocesses) for scratch calculation. "
        "Print what you want to see. This tool is free: it never consumes your tool budget, "
        "so prefer it for any arithmetic or probability checking."
    ),
    args_model=RunPythonArgs,
    fn=_run_python,
)
