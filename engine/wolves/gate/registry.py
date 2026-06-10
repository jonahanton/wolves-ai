"""The single record deciding which model produces published numbers."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wolves.config import Settings
from wolves.gate.encompassing import EncompassingResult
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import CHAMPION

logger = logging.getLogger(__name__)

ELO_CHAMPION_ID = "elo-baseline"


class ChampionRecord(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    model_version: str
    dataset_id: str
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
        dataset_id="none",
        blend_weight=0.0,
        promoted_at="2026-06-09",
        rationale="Founding engine; ships until a gated challenger is promoted.",
    )


class ChampionRegistry:
    def __init__(self, settings: Settings) -> None:
        self._artifacts = ArtifactStore(settings)

    def load(self) -> ChampionRecord:
        body = self._artifacts.get(CHAMPION)
        if body is not None:
            return ChampionRecord.model_validate_json(body)
        logger.info("no champion record found; using the Elo baseline")
        return elo_baseline()

    def promote(self, record: ChampionRecord) -> Path:
        key = self._artifacts.put(CHAMPION, record.model_dump_json(indent=2))
        logger.info("champion %s@%s promoted", record.model_id, record.model_version)
        return self._artifacts.local_path(key)
