from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RunStatus = Literal["completed", "failed"]


class RunRecord(BaseModel):
    """One row in the run index; mirrors the DynamoDB item under PK=RUN."""

    run_id: str
    created_at: str
    s3_key: str
    status: RunStatus
    cost: float
    duration_s: float
    kind: str
