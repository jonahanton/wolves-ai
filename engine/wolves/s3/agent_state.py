"""Pull/push agent memory; production filesystems are ephemeral."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import CALIBRATION, LESSONS, RUN_JOURNAL

if TYPE_CHECKING:
    from wolves.config import Settings

logger = logging.getLogger(__name__)


class AgentStateStore:
    """Mirror agent memory between the local runs root and the bucket."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def pull(self) -> int:
        """Hydrate local agent state; return the file count (0 on cold start)."""
        pulled = self._artifacts.sync_down(prefix=LESSONS.prefix)
        pulled += self._artifacts.sync_down(prefix=RUN_JOURNAL.prefix, suffix="/journal.md")
        logger.info("agent state: %d file(s) hydrated", pulled)
        return pulled

    def push(self, *, run_id: str) -> int:
        """Upload lessons, the calibration ledger and this run's journal."""
        pushed = 0
        for spec, parts in ((LESSONS, {}), (CALIBRATION, {}), (RUN_JOURNAL, {"run_id": run_id})):
            path = self._artifacts.local_path(spec.key(**parts))
            if not path.exists():
                continue
            self._artifacts.put(spec, path.read_text(encoding="utf-8"), **parts)
            pushed += 1
        logger.info("agent state: pushed %d file(s)", pushed)
        return pushed


def build_agent_state_store(settings: Settings) -> AgentStateStore | None:
    """Return the store when cloud storage is on, else None for pure-local runs."""
    if settings.storage_mode == "local":
        return None
    return AgentStateStore(ArtifactStore(settings))
