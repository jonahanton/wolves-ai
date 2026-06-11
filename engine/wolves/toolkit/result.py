from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["web", "document", "other"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    title: str
    source_type: SourceType = "other"
    published_at: str | None = None
    organisation: str | None = None
    snippet: str | None = None


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    retryable: bool = False


class ToolResult[T](BaseModel):
    """Wire-portable return contract for every shared tool.

    Tools never format markers, mint citation refs, emit display chunks,
    consume budgets, or truncate. Hosts apply those concerns by inspecting
    this structured object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ok: bool = True
    payload: T
    sources: list[SourceRef] = Field(default_factory=list)
    error: ToolError | None = None
