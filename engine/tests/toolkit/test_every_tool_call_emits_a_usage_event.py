from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from wolves.toolkit.adapters.pydantic_ai import _build_tool
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolResult


class _Args(BaseModel):
    team: str = "england"


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


async def _ok(args, deps):
    return ToolResult(payload={"fine": True})


async def _boom(args, deps):
    raise ValueError("bad team id")


async def test_success_and_failure_both_emit_tool_call_events():
    deps = _Deps(runtime=_Runtime())
    for fn in (_ok, _boom):
        spec = ToolSpec(name=f"tool_{fn.__name__}", description="x", args_model=_Args, fn=fn)
        tool = _build_tool(spec, None, lambda s, a, c, r: _json(r), None)
        await tool.function(_Ctx(deps), team="england")

    kinds = [(k, p["tool"], p["ok"]) for k, _, _, p in deps.runtime.events if k == "tool_call"]
    assert kinds == [("tool_call", "tool__ok", True), ("tool_call", "tool__boom", False)]
    assert all(actor == "quant-1" for k, actor, _, _ in deps.runtime.events)


async def _json(result):
    return result.model_dump_json()
