"""Champion registry: the single record deciding which model produces
published numbers. Lives in S3 beside the agent state, cached locally so dev
and CI work offline; nothing outside this module decides what ships."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wolves.config import Settings
from wolves.gate.encompassing import EncompassingResult
from wolves.store.artifacts import ArtifactStore

logger = logging.getLogger(__name__)

CHAMPION_KEY = "models/champion.json"
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
        body = self._artifacts.get_text(CHAMPION_KEY, prefer="s3")
        if body is not None:
            return ChampionRecord.model_validate_json(body)
        logger.info("no champion record found; using the Elo baseline")
        return elo_baseline()

    def promote(self, record: ChampionRecord) -> Path:
        self._artifacts.put_text(CHAMPION_KEY, record.model_dump_json(indent=2))
        logger.info("champion %s@%s promoted", record.model_id, record.model_version)
        return self._artifacts.local_path(CHAMPION_KEY)
