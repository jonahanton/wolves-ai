"""Per-tool wall-clock timeout for network-bound tool bodies.

An agent loop has no built-in per-tool timeout; a wedged API call will
block the whole turn indefinitely. ``run_with_timeout`` wraps an awaitable
in ``asyncio.wait_for`` so every network tool has the same ceiling, with
the timeout value sourced from ``settings.tool_timeout_seconds``.

The helper re-raises :class:`ToolTimeoutError` on breach so callers can
render a tool-specific user-facing message. Swallowing here would lose
that context; each tool already has a ``try/except`` around its I/O.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from wolves.agent_tools.errors import ToolTimeoutError
from wolves.config import get_settings


async def run_with_timeout[T](
    coro: Awaitable[T],
    *,
    tool_name: str,
    timeout_seconds: float | None = None,
) -> T:
    """Await ``coro`` with a wall-clock ceiling.

    ``timeout_seconds=None`` (the default) reads ``settings.tool_timeout_seconds``
    so callers do not have to thread the setting through themselves. Pass an
    explicit value to override for a specific call site.
    """
    if timeout_seconds is None:
        timeout_seconds = float(get_settings().tool_timeout_seconds)
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise ToolTimeoutError(tool_name, timeout_seconds) from exc
