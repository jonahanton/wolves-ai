from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wolves.observability import CapExceeded, Caps, InMemoryTracer, build_runtime


def _run_agent(*args: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "wolves.run_agent", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_live_refuses_without_anthropic_key():
    result = _run_agent("--live", "--confirm-spend", env_overrides={"ANTHROPIC_API_KEY": ""})
    assert result.returncode == 2
    assert "ANTHROPIC_API_KEY" in result.stderr


def test_live_refuses_without_confirm_spend():
    result = _run_agent("--live", env_overrides={"ANTHROPIC_API_KEY": "dummy"})
    assert result.returncode == 2
    assert "--confirm-spend" in result.stderr


def test_live_refuses_ceiling_above_absolute_max():
    result = _run_agent(
        "--live",
        "--confirm-spend",
        "--ceiling",
        "9.50",
        env_overrides={"ANTHROPIC_API_KEY": "dummy"},
    )
    assert result.returncode == 2
    assert "--ceiling" in result.stderr


def test_dollar_ceiling_cap_halts_further_llm_calls(tmp_path: Path):
    runtime = build_runtime(
        run_id="cap-run",
        tracer=InMemoryTracer(),
        caps=Caps(max_cost_micros=1_000),
        runs_root=tmp_path,
    )
    with runtime.observe(kind="run", actor="test"):
        runtime.charge_llm()
        runtime.add_cost(2_000)
        with pytest.raises(CapExceeded, match="max_cost_micros"):
            runtime.charge_llm()
    runtime.shutdown()
