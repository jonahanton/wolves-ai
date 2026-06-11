from __future__ import annotations

import json
from dataclasses import dataclass, field

from pydantic import BaseModel

from wolves.toolkit.adapters.pydantic_ai import _build_tool
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class _Args(BaseModel):
    weight: float


@dataclass
class _Runtime:
    events: list[tuple] = field(default_factory=list)

    def emit(self, kind, actor, message, **payload):
        self.events.append((kind, actor, message, payload))


@dataclass
class _Deps:
    runtime: _Runtime
    actor: str = "quant-1"


class _Ctx:
    def __init__(self, deps):
        self.deps = deps


async def _fn(args, deps):
    return ToolResult(payload={"weight": args.weight})


async def test_unparseable_arguments_come_back_as_a_correctable_error():
    spec = ToolSpec(name="reweight", description="x", args_model=_Args, fn=_fn)
    tool = _build_tool(spec, None, lambda s, a, c, r: _json(r), None)
    deps = _Deps(runtime=_Runtime())

    raw = await tool.function(_Ctx(deps), weight="heavy")

    result = json.loads(raw)
    assert result["ok"] is False
    assert result["error"]["type"] == "invalid_arguments"
    assert tool.max_retries == 3


async def _json(result):
    return result.model_dump_json()
