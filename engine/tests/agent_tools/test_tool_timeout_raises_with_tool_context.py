from __future__ import annotations

import asyncio

import pytest

from wolves.agent_tools._timeout import run_with_timeout
from wolves.agent_tools.errors import ToolTimeoutError


async def test_returns_result_when_fast_enough():
    async def quick() -> int:
        return 42

    assert await run_with_timeout(quick(), tool_name="quick", timeout_seconds=1.0) == 42


async def test_raises_tool_timeout_error_with_tool_name_and_seconds():
    async def slow() -> None:
        await asyncio.sleep(5)

    with pytest.raises(ToolTimeoutError) as exc_info:
        await run_with_timeout(slow(), tool_name="slow_tool", timeout_seconds=0.05)

    assert exc_info.value.tool_name == "slow_tool"
    assert exc_info.value.timeout_seconds == pytest.approx(0.05)
    assert "slow_tool" in str(exc_info.value)
    assert "timed out" in str(exc_info.value)


async def test_timeout_default_sourced_from_settings(monkeypatch: pytest.MonkeyPatch):
    from wolves import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("TOOL_TIMEOUT_SECONDS", "0.05")
    try:

        async def slow() -> None:
            await asyncio.sleep(5)

        with pytest.raises(ToolTimeoutError) as exc_info:
            await run_with_timeout(slow(), tool_name="default_timeout")

        assert exc_info.value.timeout_seconds == pytest.approx(0.05)
    finally:
        config.get_settings.cache_clear()


async def test_propagates_non_timeout_exceptions_untouched():
    class BoomError(RuntimeError):
        pass

    async def explode() -> None:
        raise BoomError("nope")

    with pytest.raises(BoomError, match="nope"):
        await run_with_timeout(explode(), tool_name="boom", timeout_seconds=1.0)
