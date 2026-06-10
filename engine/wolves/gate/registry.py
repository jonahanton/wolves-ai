"""Champion registry: the single record deciding which model produces
published numbers. Lives in S3 beside the agent state, cached locally so dev
and CI work offline; nothing outside this module decides what ships."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wolves.clients.s3.client import S3Client
from wolves.config import Settings
from wolves.gate.encompassing import EncompassingResult

logger = logging.getLogger(__name__)

S3_KEY = "models/champion.json"
ELO_CHAMPION_ID = "elo-baseline"


class ChampionRecord(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    model_version: str
    dataset_version: str
    half_life_days: float | None = None
    blend_weight: float
    promoted_at: str
    rationale: str
    gate_report: EncompassingResult | None = None


def elo_baseline() -> ChampionRecord:
    """The standing champion when no gate report has ever been published."""
    return ChampionRecord(
        model_id=ELO_CHAMPION_ID,
        model_version="0",
        dataset_version="none",
        blend_weight=0.0,
        promoted_at="2026-06-09",
        rationale="Founding engine; ships until a gated challenger is promoted.",
    )


class ChampionRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._local = settings.runs_root / "models" / "champion.json"

    def load(self) -> ChampionRecord:
        if self._settings.agent_state_bucket:
            s3 = S3Client(bucket=self._settings.agent_state_bucket, region=self._settings.aws_region)
            body = s3.get_text(S3_KEY)
            if body is not None:
                return ChampionRecord.model_validate_json(body)
        if self._local.exists():
            return ChampionRecord.model_validate_json(self._local.read_text(encoding="utf-8"))
        logger.info("no champion record found; using the Elo baseline")
        return elo_baseline()

    def promote(self, record: ChampionRecord) -> Path:
        self._local.parent.mkdir(parents=True, exist_ok=True)
        self._local.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        if self._settings.agent_state_bucket:
            s3 = S3Client(bucket=self._settings.agent_state_bucket, region=self._settings.aws_region)
            s3.put_text(S3_KEY, record.model_dump_json(indent=2), content_type="application/json")
            logger.info("champion %s@%s promoted to S3", record.model_id, record.model_version)
        return self._local
