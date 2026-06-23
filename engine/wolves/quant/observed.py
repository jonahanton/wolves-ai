from __future__ import annotations

from wolves.observability.runtime import ObservedRuntime
from wolves.quant.context import SandboxContext
from wolves.quant.executor import QuantExecutionResult, run_analysis
from wolves.quant.workspace import QuantWorkspace, WorkspaceArtifact


class ObservedQuant:
    """The only way agents reach the quant workbench. Writes are observed
    workspace spans; execution is charged against caps and observed."""

    def __init__(self, runtime: ObservedRuntime) -> None:
        self._runtime = runtime
        self._quant_root = runtime.paths.workspace / "quant"

    def workspace(self, node_id: str) -> QuantWorkspace:
        return QuantWorkspace(self._quant_root, node_id)

    def write_context(self, workspace: QuantWorkspace, context: SandboxContext) -> None:
        """Refresh the sandbox context before each script."""
        workspace.write("context.json", context.model_dump_json(indent=1), in_inputs=True)

    def write_analysis(self, *, actor: str, workspace: QuantWorkspace, code: str, filename: str) -> WorkspaceArtifact:
        with self._runtime.observe(
            kind="workspace_write",
            actor=actor,
            name=f"write:{filename}",
            input={"filename": filename, "bytes": len(code.encode())},
        ) as rec:
            art = workspace.write(filename, code)
            rec.set_output({"path": art.path, "content_hash": art.content_hash})
            rec.note(
                summary=f"wrote {filename} ({art.byte_count}B)",
                path=art.path,
                content_hash=art.content_hash,
                byte_count=art.byte_count,
            )
            return art

    async def execute(self, *, actor: str, workspace: QuantWorkspace, script: str) -> QuantExecutionResult:
        self._runtime.charge_quant()
        code_preview = (workspace.dir / script).read_text(encoding="utf-8")[:800]
        with self._runtime.observe(
            kind="quant_exec",
            actor=actor,
            name=f"quant_exec:{workspace.dir.name}/{script}",
            input={"code_preview": code_preview},
        ) as rec:
            result = await run_analysis(workspace, script=script, caps=self._runtime.caps)
            if not result.ok:
                rec.annotate(severity="error", failure_category="quant_execution")
            result.trace_id = rec.trace_id
            result.observation_id = rec.observation_id
            rec.set_output(
                {
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "duration_s": result.duration_seconds,
                    "usage": result.usage,
                    "outputs": [o.filename for o in result.output_files],
                    "stdout_tail": result.stdout[-1500:],
                    "stderr_tail": result.stderr[-1500:],
                }
            )
            status = "ok" if result.ok else "FAIL"
            failure_tails = (
                {"stdout_tail": result.stdout[-1500:], "stderr_tail": result.stderr[-1500:]} if not result.ok else {}
            )
            rec.note(
                summary=f"exec {script} -> {status} ({result.duration_seconds}s, {len(result.output_files)} outputs)",
                exit_code=result.exit_code,
                timed_out=result.timed_out,
                code_hash=result.code_hash,
                output_files=[o.dataset_id for o in result.output_files],
                package_versions=result.package_versions,
                error=result.error,
                **failure_tails,
            )
            return result
