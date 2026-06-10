from __future__ import annotations

from pathlib import Path

from wolves.observability.budget import Caps
from wolves.quant.executor import run_analysis
from wolves.quant.workspace import QuantWorkspace

_OK_CODE = """\
import json
from pathlib import Path

Path("outputs").mkdir(exist_ok=True)
Path("outputs/result.json").write_text(json.dumps({"p": 0.34}))
print("p 0.34")
result = {"p": 0.34}
"""

_NO_RESULT_CODE = """\
print("forgot the contract")
"""

_NETWORK_CODE = """\
import socket
socket.create_connection(("example.com", 443))
"""

_SPAWN_CODE = """\
import subprocess
subprocess.Popen(["echo", "hi"])
"""

_SLEEP_CODE = """\
import time
time.sleep(30)
"""


def _workspace(tmp_path: Path, code: str) -> QuantWorkspace:
    workspace = QuantWorkspace(tmp_path, "node-1")
    workspace.write("analysis_001.py", code)
    return workspace


async def test_executes_and_manifests_outputs(tmp_path: Path):
    workspace = _workspace(tmp_path, _OK_CODE)
    result = await run_analysis(workspace, script="analysis_001.py", caps=Caps.small())
    assert result.ok and result.exit_code == 0
    assert result.result_value == {"p": 0.34}
    assert any(o.filename == "result.json" for o in result.output_files)
    assert "p 0.34" in result.stdout
    assert result.code_hash.startswith("sha256:")


async def test_missing_result_is_a_structured_error(tmp_path: Path):
    workspace = _workspace(tmp_path, _NO_RESULT_CODE)
    result = await run_analysis(workspace, script="analysis_001.py", caps=Caps.small())
    assert not result.ok
    assert result.no_result
    assert result.error and "`result` was never assigned" in result.error


async def test_network_access_is_blocked(tmp_path: Path):
    workspace = _workspace(tmp_path, _NETWORK_CODE)
    result = await run_analysis(workspace, script="analysis_001.py", caps=Caps.small())
    assert not result.ok
    assert "network access is disabled" in result.stderr


async def test_process_spawn_is_blocked(tmp_path: Path):
    workspace = _workspace(tmp_path, _SPAWN_CODE)
    result = await run_analysis(workspace, script="analysis_001.py", caps=Caps.small())
    assert not result.ok
    assert "disabled inside the quant sandbox" in result.stderr


async def test_timeout_kills_the_process(tmp_path: Path):
    workspace = _workspace(tmp_path, _SLEEP_CODE)
    result = await run_analysis(workspace, script="analysis_001.py", caps=Caps.small(), timeout_seconds=1)
    assert not result.ok
    assert result.timed_out
    assert result.error and "timed out" in result.error
    assert result.duration_seconds < 10


async def test_output_over_byte_cap_fails(tmp_path: Path):
    """RLIMIT_FSIZE inside the sandbox stops the oversized write itself."""
    code = """\
from pathlib import Path
Path("outputs").mkdir(exist_ok=True)
Path("outputs/big.bin").write_bytes(b"x" * 5000)
"""
    workspace = _workspace(tmp_path, code)
    caps = Caps.small().model_copy(update={"max_quant_bytes": 1024})
    result = await run_analysis(workspace, script="analysis_001.py", caps=caps)
    assert not result.ok
    assert "File too large" in result.stderr
    assert result.output_bytes <= 1024
