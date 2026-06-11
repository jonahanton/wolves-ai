from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from pydantic import BaseModel

from wolves.toolkit.result import ToolResult

type ToolFn[ArgsT: BaseModel, ResultT] = Callable[[ArgsT, Any], Awaitable[ToolResult[ResultT]]]


@dataclass(frozen=True)
class ToolSpec[ArgsT: BaseModel, ResultT]:
    """A framework-agnostic tool definition.

    A tool is `(name, description, args_model, fn)`. Adapters render it
    out: ``adapters/pydantic_ai`` mounts it on an ``Agent`` toolset.

    ``fn`` is an async callable with the signature ``(args, deps) ->
    ToolResult``. ``deps`` is whatever the host provides; the spec is
    deliberately untyped on that axis so a tool can declare its required
    Protocol via ``deps.py`` without constraining adapters.
    """

    name: str
    description: str
    args_model: type[ArgsT]
    fn: ToolFn[ArgsT, ResultT]

    @cached_property
    def json_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()
