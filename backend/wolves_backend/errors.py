from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str


class UpstreamError(Exception):
    """An AWS dependency call failed; maps to a 502 at the route boundary."""

    def __init__(self, service: str, detail: str) -> None:
        self.service = service
        self.detail = detail
        super().__init__(f"{service}: {detail}")
