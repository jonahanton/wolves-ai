"""Cross-run agent memory persisted to S3. Production filesystems are
ephemeral, so LESSONS.md, the calibration ledger and run journals are pulled
before an agent run and pushed after it; without this every run starts with
amnesia. With no bucket configured the factory returns None and local dev
behaves exactly as before."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from wolves.clients.s3 import S3Client

if TYPE_CHECKING:
    from pathlib import Path

    from wolves.config import Settings

logger = logging.getLogger(__name__)

_LESSONS_KEY = "LESSONS.md"
_CALIBRATION_KEY = "calibration.jsonl"
_JOURNALS = "journals"
_JOURNAL_NAME = "journal.md"


class AgentStateStore:
    """Mirror agent memory files between the local runs root and one S3 prefix."""

    def __init__(
        self,
        *,
        s3: S3Client,
        prefix: str,
        lessons_path: Path,
        calibration_path: Path,
        runs_root: Path,
    ) -> None:
        self._s3 = s3
        self._prefix = prefix.strip("/")
        self._lessons_path = lessons_path
        self._calibration_path = calibration_path
        self._runs_root = runs_root

    def pull(self) -> int:
        """Download all persisted state; return the file count (0 on cold start)."""
        pulled = 0
        for key in self._s3.list_keys(prefix=f"{self._prefix}/"):
            path = self._local_path(key)
            if path is None:
                logger.warning("ignoring unexpected agent-state key %s", key)
                continue
            body = self._s3.get_text(key)
            if body is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            pulled += 1
        logger.info("agent state: pulled %d file(s) from s3://%s/%s", pulled, self._s3.bucket, self._prefix)
        return pulled

    def push(self, *, run_id: str) -> int:
        """Upload lessons, the calibration ledger and this run's journal."""
        targets = (
            (self._lessons_path, f"{self._prefix}/{_LESSONS_KEY}"),
            (self._calibration_path, f"{self._prefix}/{_CALIBRATION_KEY}"),
            (self._runs_root / run_id / _JOURNAL_NAME, f"{self._prefix}/{_JOURNALS}/{run_id}/{_JOURNAL_NAME}"),
        )
        pushed = 0
        for path, key in targets:
            if not path.exists():
                continue
            self._s3.put_text(key, path.read_text(encoding="utf-8"))
            pushed += 1
        logger.info("agent state: pushed %d file(s) to s3://%s/%s", pushed, self._s3.bucket, self._prefix)
        return pushed

    def _local_path(self, key: str) -> Path | None:
        relative = key.removeprefix(f"{self._prefix}/")
        if relative == _LESSONS_KEY:
            return self._lessons_path
        if relative == _CALIBRATION_KEY:
            return self._calibration_path
        parts = relative.split("/")
        if len(parts) == 3 and parts[0] == _JOURNALS and parts[2] == _JOURNAL_NAME and parts[1] not in {"", ".", ".."}:
            return self._runs_root / parts[1] / _JOURNAL_NAME
        return None


def build_agent_state_store(settings: Settings) -> AgentStateStore | None:
    """Return the store when an agent-state bucket is configured, else None."""
    if not settings.agent_state_bucket:
        return None
    return AgentStateStore(
        s3=S3Client(bucket=settings.agent_state_bucket, region=settings.aws_region),
        prefix=settings.agent_state_prefix,
        lessons_path=settings.lessons_path,
        calibration_path=settings.calibration_path,
        runs_root=settings.runs_root,
    )
