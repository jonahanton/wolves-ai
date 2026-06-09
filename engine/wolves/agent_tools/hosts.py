from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)

WEB = "web"

_DEFAULT_HOSTS = (WEB,)


@dataclass(frozen=True, slots=True)
class HostLimits:
    _slots: Mapping[str, asyncio.Semaphore]
    _capacities: Mapping[str, int]

    @classmethod
    def from_capacities(cls, capacities: Mapping[str, int]) -> HostLimits:
        normalised = {host: max(1, capacity) for host, capacity in capacities.items()}
        return cls(
            _slots={host: asyncio.Semaphore(cap) for host, cap in normalised.items()},
            _capacities=normalised,
        )

    @classmethod
    def unlimited(cls) -> HostLimits:
        caps = {h: 1_000_000 for h in _DEFAULT_HOSTS}
        return cls(
            _slots={h: asyncio.Semaphore(c) for h, c in caps.items()},
            _capacities=caps,
        )

    @asynccontextmanager
    async def slot(self, host: str) -> AsyncIterator[None]:
        sem = self._slots.get(host)
        if sem is None:
            logger.debug("host_limits: unknown host %r, no serialisation", host)
            yield
            return
        async with sem:
            yield

    def capacity(self, host: str) -> int | None:
        return self._capacities.get(host)
