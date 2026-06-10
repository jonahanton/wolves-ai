"""Cross-run agent memory. Production filesystems are ephemeral, so lessons,
the calibration ledger and run journals are pulled before an agent run and
pushed after it; without this every run starts with amnesia."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wolves.agent.memory import run_dir
from wolves.store.artifacts import ArtifactStore

if TYPE_CHECKING:
    from wolves.config import Settings

logger = logging.getLogger(__name__)

_PREFIX = "agent-state"
_JOURNAL_NAME = "journal.md"


class AgentStateStore:
    """Mirror agent memory between the local runs root and the bucket."""

    def __init__(self, *, artifacts: ArtifactStore, settings: Settings) -> None:
        self._artifacts = artifacts
        self._settings = settings

    def pull(self) -> int:
        """Hydrate local agent state; return the file count (0 on cold start)."""
        pulled = self._artifacts.sync_down(prefix=f"{_PREFIX}/")
        pulled += self._artifacts.sync_down(prefix="runs/", suffix=_JOURNAL_NAME)
        logger.info("agent state: %d file(s) hydrated", pulled)
        return pulled

    def push(self, *, run_id: str) -> int:
        """Upload lessons, the calibration ledger and this run's journal."""
        targets = (
            (self._settings.lessons_path, f"{_PREFIX}/lessons.jsonl"),
            (self._settings.calibration_path, f"{_PREFIX}/calibration.jsonl"),
            (run_dir(self._settings.runs_root, run_id) / _JOURNAL_NAME, f"runs/{run_id}/{_JOURNAL_NAME}"),
        )
        pushed = 0
        for path, key in targets:
            if not path.exists():
                continue
            self._artifacts.put_text(key, path.read_text(encoding="utf-8"), content_type="text/plain; charset=utf-8")
            pushed += 1
        logger.info("agent state: pushed %d file(s)", pushed)
        return pushed


def build_agent_state_store(settings: Settings) -> AgentStateStore | None:
    """Return the store when cloud storage is on, else None for pure-local runs."""
    if settings.storage_mode == "local":
        return None
    return AgentStateStore(artifacts=ArtifactStore(settings), settings=settings)
