"""Pull/push agent memory; production filesystems are ephemeral."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import CALIBRATION, LESSONS, RUN_ARTIFACT_INDEX, RUN_JOURNAL, SNAPSHOT

if TYPE_CHECKING:
    from wolves.config import Settings

logger = logging.getLogger(__name__)


class AgentStateStore:
    """Mirror agent memory between the local runs root and the bucket."""

    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def pull(self) -> int:
        """Hydrate local agent state; return the file count (0 on cold start)."""
        # Mutable pointers refresh through get(), which treats the bucket as
        # authoritative; sync_down would keep a stale local copy.
        pulled = sum(1 for spec in (LESSONS, CALIBRATION) if self._artifacts.get(spec) is not None)
        pulled += self._artifacts.sync_down(prefix=RUN_JOURNAL.prefix)
        # Yesterday's snapshots feed calibration scoring and live overrides.
        pulled += self._artifacts.sync_down(prefix=SNAPSHOT.prefix)
        logger.info("agent state: %d file(s) hydrated", pulled)
        return pulled

    def push(self, *, run_id: str) -> int:
        """Upload cross-run state and everything this run produced."""
        pushed = 0
        for spec, parts in (
            (LESSONS, {}),
            (CALIBRATION, {}),
            (RUN_JOURNAL, {"run_id": run_id}),
            (RUN_ARTIFACT_INDEX, {"run_id": run_id}),
        ):
            path = self._artifacts.local_path(spec.key(**parts))
            if not path.exists():
                continue
            self._artifacts.put(spec, path.read_text(encoding="utf-8"), **parts)
            pushed += 1
        # Immutable run files (artifacts, events, workspace) ride one sweep.
        pushed += self._artifacts.sync_up(prefix=f"runs/{run_id}/")
        logger.info("agent state: pushed %d file(s)", pushed)
        return pushed


def build_agent_state_store(settings: Settings) -> AgentStateStore | None:
    """Return the store when cloud storage is on, else None for pure-local runs."""
    if settings.storage_mode == "local":
        return None
    return AgentStateStore(ArtifactStore(settings))
