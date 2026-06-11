from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from typing import TYPE_CHECKING

from wolves.agent.deps import AgentDeps
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

if TYPE_CHECKING:
    from wolves.graph.artifacts import RunArtifactStore

_FILE_CHARS = 12_000


class ReadArtifactArgs(BaseModel):
    artifact_id: str
    run_id: str | None = None
    file: str | None = None


def _error(kind: str, message: str) -> ToolResult[Any]:
    return ToolResult(ok=False, payload=None, error=ToolError(type=kind, message=message))


def _read_file(store: RunArtifactStore, artifact_id: str, name: str) -> dict[str, str] | ToolResult[Any]:
    base = store.workspace_path(artifact_id)
    if base is None:
        return _error("no_workspace", f"artifact {artifact_id!r} left no workspace files")
    root = Path(base).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        return _error("bad_path", "file paths are relative to the artifact's workspace")
    if not path.is_file():
        listing = ", ".join(store.workspace_files(artifact_id)) or "(empty)"
        return _error("unknown_file", f"no file {name!r}; workspace holds: {listing}")
    return {"name": name, "content": path.read_text(encoding="utf-8", errors="replace")[:_FILE_CHARS]}


async def _read_artifact(args: ReadArtifactArgs, deps: AgentDeps) -> ToolResult[Any]:
    # Imported lazily: the graph package init mounts the toolsets that import
    # this module, so a top-level import is circular.
    from wolves.graph.artifacts import MissingRunIndexError, RunArtifactStore
    from wolves.s3.artifacts import ArtifactStore

    store = deps.artifacts
    if args.run_id is not None and (store is None or args.run_id != store.run_id):
        try:
            store = RunArtifactStore.open_run(ArtifactStore(deps.settings), args.run_id)
        except MissingRunIndexError:
            return _error("unknown_run", f"no archived artifact index for run {args.run_id!r}")
    if store is None:
        return _error("no_artifact_store", "this run has no artifact store")
    artifact = store.get(args.artifact_id)
    if artifact is None:
        known = ", ".join(r.id for r in store.all()) or "(none yet)"
        return _error("unknown_artifact", f"no artifact {args.artifact_id!r}; known ids: {known}")
    payload: dict[str, Any] = artifact.model_dump(mode="json")
    files = store.workspace_files(artifact.id)
    if files:
        payload["workspace_files"] = files
    if args.file is not None:
        read = _read_file(store, artifact.id, args.file)
        if isinstance(read, ToolResult):
            return read
        payload["file"] = read
    return ToolResult(payload=payload)


SPEC = ToolSpec(
    name="read_artifact",
    description=(
        "Open one artifact by id: its full typed payload, plus its workspace file listing when the "
        "producing node left files behind (quant analyses do). Defaults to this run; pass run_id to "
        "open any archived run's artifact (previous_forecast lists them), and file to read one "
        "workspace file's content, e.g. a past quant's analysis_003.py. Your brief lists the "
        "artifact ids you were given; the blackboard summary names everything else."
    ),
    args_model=ReadArtifactArgs,
    fn=_read_artifact,
)
