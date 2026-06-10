from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
import time
from typing import Any

from pydantic import BaseModel, Field

from wolves.observability.budget import Caps
from wolves.quant.context import available_packages
from wolves.quant.workspace import QuantWorkspace, content_hash

_MAX_CAPTURE_CHARS = 20_000
_RESULT_MARKER = "__WQ_RESULT__:"

NO_RESULT_MESSAGE = (
    "No value was returned: assign the finding to `result` at the end of the script "
    "(a bare expression or print() does not count)."
)

# Hardens the child before running the analysis script: blocks the network and
# the process-spawn/exec surface and sets CPU/file-size rlimits. Best-effort for
# LLM-written code, not an adversary-proof jail (native code can still escape).
# The workbench namespace (wq, pd, np) is preloaded and the script's trailing
# `result` assignment is emitted on a marker line for the host to parse.
_RUNNER = """\
import os, socket

def _no_network(*args, **kwargs):
    raise OSError("network access is disabled inside the quant sandbox")

socket.socket.connect = _no_network
socket.socket.connect_ex = _no_network
socket.create_connection = _no_network

def _no_spawn(*args, **kwargs):
    raise OSError("spawning or replacing processes is disabled inside the quant sandbox")

for _name in (
    "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
    "execv", "execve", "execvp", "execvpe", "execl", "execle", "execlp", "execlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe", "spawnl", "spawnle", "spawnlp", "spawnlpe",
):
    if hasattr(os, _name):
        setattr(os, _name, _no_spawn)
try:
    import subprocess
    subprocess.Popen = _no_spawn
except Exception:
    pass

try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, ({cpu}, {cpu}))
    resource.setrlimit(resource.RLIMIT_FSIZE, ({fsize}, {fsize}))
except Exception:
    pass

import json as _json
import numpy as np
import pandas as pd
import wolves.quant.wolves_quant as wq

_ns = {{"__name__": "__main__", "wq": wq, "pd": pd, "np": np, "result": None}}
_code = open({script!r}, encoding="utf-8").read()
try:
    exec(compile(_code, {script!r}, "exec"), _ns)
finally:
    wq._finalise()
print("\\n{marker}" + _json.dumps(wq._sanitise(_ns.get("result")), default=str))
"""


def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill the child's whole session so spawned grandchildren die with it."""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


class DataManifestEntry(BaseModel):
    dataset_id: str
    filename: str
    path: str
    content_hash: str
    byte_count: int


class QuantExecutionResult(BaseModel):
    ok: bool
    exit_code: int
    timed_out: bool = False
    duration_seconds: float
    stdout: str = ""
    stderr: str = ""
    code_path: str
    code_hash: str
    result_value: Any = None
    no_result: bool = False
    usage: dict[str, int] = Field(default_factory=dict)
    output_files: list[DataManifestEntry] = Field(default_factory=list)
    output_bytes: int = 0
    package_versions: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    trace_id: str | None = None
    observation_id: str | None = None


def _split_result(raw_stdout: str) -> tuple[str, Any, bool]:
    """Separate the printed stream from the marker-carried result value."""
    marker_at = raw_stdout.rfind(_RESULT_MARKER)
    if marker_at < 0:
        return raw_stdout, None, True
    stream = raw_stdout[:marker_at].rstrip("\n")
    payload = raw_stdout[marker_at + len(_RESULT_MARKER) :].strip()
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return stream, None, True
    return stream, value, value is None


async def run_analysis(
    workspace: QuantWorkspace,
    *,
    script: str,
    caps: Caps,
    timeout_seconds: int | None = None,
) -> QuantExecutionResult:
    """Execute one analysis script in the node workspace under hard caps."""
    script_path = workspace.dir / script
    if not script_path.exists():
        raise FileNotFoundError(f"no {script} at {script_path}")

    code = script_path.read_bytes()
    timeout = timeout_seconds or caps.max_quant_runtime_seconds
    runner_path = workspace.dir / "_runner.py"
    runner_path.write_text(
        _RUNNER.format(cpu=timeout + 5, fsize=caps.max_quant_bytes, script=script, marker=_RESULT_MARKER),
        encoding="utf-8",
    )

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONUNBUFFERED": "1",
        "MPLBACKEND": "Agg",
        "STORAGE_MODE": "local",
    }
    if "VIRTUAL_ENV" in os.environ:
        env["VIRTUAL_ENV"] = os.environ["VIRTUAL_ENV"]

    started = time.monotonic()
    timed_out = False
    error: str | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "_runner.py",
            cwd=str(workspace.dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            exit_code = proc.returncode if proc.returncode is not None else -1
        except TimeoutError:
            timed_out = True
            _kill_process_group(proc)
            out_b, err_b = await proc.communicate()
            exit_code = -1
            error = f"timed out after {timeout}s"
    except Exception as exc:
        return QuantExecutionResult(
            ok=False,
            exit_code=-1,
            duration_seconds=round(time.monotonic() - started, 3),
            code_path=str(script_path),
            code_hash=content_hash(code),
            package_versions=available_packages(),
            error=f"{type(exc).__name__}: {exc}",
        )

    duration = round(time.monotonic() - started, 3)
    raw_stdout = out_b.decode("utf-8", "replace")
    stderr = err_b.decode("utf-8", "replace")[:_MAX_CAPTURE_CHARS]
    stream, result_value, no_result = _split_result(raw_stdout)
    stdout = stream[:_MAX_CAPTURE_CHARS]
    (workspace.outputs / f"_{script_path.stem}.stdout.txt").write_text(raw_stdout, encoding="utf-8")

    outputs = [
        DataManifestEntry(
            dataset_id=f"{workspace.dir.name}:{art.filename}",
            filename=art.filename,
            path=art.path,
            content_hash=art.content_hash,
            byte_count=art.byte_count,
        )
        for art in workspace.list_outputs()
        # Underscore files are host archives (stdout, usage), not analysis outputs.
        if not art.filename.split("/")[-1].startswith("_")
    ]
    output_bytes = sum(o.byte_count for o in outputs)
    over_bytes = output_bytes > caps.max_quant_bytes
    if over_bytes:
        error = (error or "") + f" output exceeded max_quant_bytes ({caps.max_quant_bytes})"

    clean_exit = exit_code == 0 and not timed_out and not over_bytes
    ok = clean_exit and not no_result
    if clean_exit and no_result:
        error = NO_RESULT_MESSAGE
    if not ok and error is None:
        error = f"exit code {exit_code}"

    return QuantExecutionResult(
        ok=ok,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
        code_path=str(script_path),
        code_hash=content_hash(code),
        result_value=result_value,
        no_result=no_result,
        usage=workspace.read_usage(),
        output_files=outputs,
        output_bytes=output_bytes,
        package_versions=available_packages(),
        error=error,
    )
