from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from wolves.agent_tools.hosts import HostLimits


@runtime_checkable
class WebFetchDeps(Protocol):
    """Per-turn dependencies for ``web_fetch``.

    Read-only from the tool's perspective. ``host_limits`` is reused
    across web tools to share a per-host concurrency cap.
    """

    host_limits: HostLimits
