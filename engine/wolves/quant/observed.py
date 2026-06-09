from __future__ import annotations

from typing import TYPE_CHECKING

from wolves.observability.runtime import ObservedRuntime
from wolves.quant.context import QuantArtifact, QuantContext, build_quant_context
from wolves.quant.executor import QuantExecutionResult, run_analysis
from wolves.quant.workspace import QuantWorkspace, WorkspaceArtifact

if TYPE_CHECKING:
    import pandas as pd


class ObservedQuant:
    """The only way agents reach the quant workbench. Writes are observed
    workspace spans; execution is charged against caps and observed."""

    def __init__(self, runtime: ObservedRuntime) -> None:
        self._runtime = runtime
        self._quant_root = runtime.paths.workspace / "quant"

    def workspace(self, node_id: str) -> QuantWorkspace:
        return QuantWorkspace(self._quant_root, node_id)

    def context(
        self,
        workspace: QuantWorkspace,
        artifacts: list[QuantArtifact],
        *,
        query_title: str,
        ask: str,
        as_of: str,
    ) -> QuantContext:
        return build_quant_context(
            query_title=query_title,
            ask=ask,
            as_of=as_of,
            workspace_dir=str(workspace.dir),
            artifacts=artifacts,
            caps=self._runtime.caps,
        )

    def seed_inputs(
        self, *, actor: str, workspace: QuantWorkspace, frames: dict[str, pd.DataFrame]
    ) -> list[WorkspaceArtifact]:
        """Persist fetched dataframes into the workspace as parquet so analysis.py
        can `pd.read_parquet("inputs/<id>.parquet")` without any network access."""
        if not frames:
            return []
        written: list[WorkspaceArtifact] = []
        with self._runtime.observe(
            kind="workspace_write",
            actor=actor,
            name=f"seed_inputs:{workspace.dir.name}",
            input={"datasets": list(frames)},
        ) as rec:
            for dataset_id, frame in frames.items():
                safe = dataset_id.replace("/", "_")
                filename = f"{safe}.parquet"
                path = workspace.inputs / filename
                frame.to_parquet(path, index=False)
                written.append(workspace.write(filename, path.read_bytes(), in_inputs=True))
            rec.set_output({"files": [a.filename for a in written]})
            rec.note(
                summary=f"seeded {len(written)} input frame(s)",
                files=[a.path for a in written],
                content_hashes=[a.content_hash for a in written],
            )
        return written

    def write_analysis(self, *, actor: str, workspace: QuantWorkspace, code: str) -> WorkspaceArtifact:
        filename = "analysis.py"
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

    async def execute(self, *, actor: str, workspace: QuantWorkspace) -> QuantExecutionResult:
        self._runtime.charge_quant()
        code_preview = workspace.analysis_path.read_text(encoding="utf-8")[:800]
        with self._runtime.observe(
            kind="quant_exec",
            actor=actor,
            name=f"quant_exec:{workspace.dir.name}",
            input={"code_preview": code_preview},
        ) as rec:
            result = await run_analysis(workspace, caps=self._runtime.caps)
            result.trace_id = rec.trace_id
            result.observation_id = rec.observation_id
            rec.set_output(
                {
                    "ok": result.ok,
                    "exit_code": result.exit_code,
                    "duration_s": result.duration_seconds,
                    "outputs": [o.filename for o in result.output_files],
                    "stdout_tail": result.stdout[-1500:],
                    "stderr_tail": result.stderr[-1500:],
                }
            )
            status = "ok" if result.ok else "FAIL"
            rec.note(
                summary=(
                    f"exec analysis.py -> {status} ({result.duration_seconds}s, {len(result.output_files)} outputs)"
                ),
                exit_code=result.exit_code,
                timed_out=result.timed_out,
                code_hash=result.code_hash,
                output_files=[o.dataset_id for o in result.output_files],
                package_versions=result.package_versions,
                error=result.error,
            )
            return result
