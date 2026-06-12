"""Fitted-state persistence: a backend boots from the published fit instead of refitting."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel

from wolves.models.contracts import FittedState
from wolves.s3.layout import FITTED_LATEST, FITTED_STATE

if TYPE_CHECKING:
    from wolves.s3.artifacts import ArtifactStore

logger = logging.getLogger(__name__)


class FittedStateRecord(BaseModel):
    """Wire shape of one FittedState; arrays become lists at full float precision."""

    model_id: str
    version: str
    dataset_id: str
    as_of: date
    teams: tuple[str, ...]
    strengths: list[float]
    globals_: dict[str, float]
    covariance: list[list[float]] | None = None
    diagnostics: dict[str, float]

    @classmethod
    def from_state(cls, state: FittedState) -> FittedStateRecord:
        return cls(
            model_id=state.model_id,
            version=state.version,
            dataset_id=state.dataset_id,
            as_of=state.as_of,
            teams=state.teams,
            strengths=state.strengths.tolist(),
            globals_=dict(state.globals_),
            covariance=state.covariance.tolist() if state.covariance is not None else None,
            diagnostics=dict(state.diagnostics),
        )

    def to_state(self) -> FittedState:
        return FittedState(
            model_id=self.model_id,
            version=self.version,
            dataset_id=self.dataset_id,
            as_of=self.as_of,
            teams=tuple(self.teams),
            strengths=np.asarray(self.strengths, dtype=float),
            globals_=dict(self.globals_),
            covariance=np.asarray(self.covariance, dtype=float) if self.covariance is not None else None,
            diagnostics=dict(self.diagnostics),
        )


class FittedPointer(BaseModel):
    run_id: str
    model_id: str
    dataset_id: str
    as_of: date
    published_at: str


class FittedStateStore:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def publish(self, state: FittedState, *, run_id: str) -> str:
        record = FittedStateRecord.from_state(state)
        key = self._artifacts.put(FITTED_STATE, record.model_dump_json(), run_id=run_id)
        pointer = FittedPointer(
            run_id=run_id,
            model_id=state.model_id,
            dataset_id=state.dataset_id,
            as_of=state.as_of,
            published_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self._artifacts.put(FITTED_LATEST, pointer.model_dump_json(indent=2))
        logger.info("published fitted state %s (%s)", run_id, state.model_id)
        return key

    def latest_pointer(self) -> FittedPointer | None:
        body = self._artifacts.get(FITTED_LATEST)
        return FittedPointer.model_validate_json(body) if body else None

    def load(self, *, run_id: str | None = None) -> FittedState | None:
        resolved = run_id
        if resolved is None:
            pointer = self.latest_pointer()
            if pointer is None:
                return None
            resolved = pointer.run_id
        body = self._artifacts.get(FITTED_STATE, run_id=resolved)
        return FittedStateRecord.model_validate_json(body).to_state() if body else None
