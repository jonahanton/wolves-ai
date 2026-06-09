from __future__ import annotations

import json

from pydantic import BaseModel

from wolves.agent_tools.adapters.anthropic import dispatch, to_anthropic_tools
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult


class _Args(BaseModel):
    q: str


async def _ok(args: _Args, deps: object) -> ToolResult:
    return ToolResult(ok=True, payload={"q": args.q})


async def _bad(args: _Args, deps: object) -> ToolResult:
    return ToolResult(ok=False, payload=None, error=ToolError(type="X", message="boom"))


def _spec(name: str = "t", fn=_ok) -> ToolSpec:
    return ToolSpec(name=name, description="d", args_model=_Args, fn=fn)


def test_to_anthropic_tools_renders_param_dict():
    out = to_anthropic_tools([_spec("foo")])
    assert out[0]["name"] == "foo"
    assert out[0]["description"] == "d"
    assert out[0]["input_schema"]["properties"].keys() == {"q"}


def test_extras_propagate_into_param():
    spec = ToolSpec(
        name="t",
        description="d",
        args_model=_Args,
        fn=_ok,
        extras={"cache_control": {"type": "ephemeral"}},
    )
    out = to_anthropic_tools([spec])
    assert out[0]["cache_control"] == {"type": "ephemeral"}


async def test_dispatch_returns_tool_result_block():
    block = await dispatch({"id": "u1", "name": "t", "input": {"q": "x"}}, [_spec()], deps=object())
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "u1"
    assert block["is_error"] is False
    assert json.loads(block["content"])["payload"] == {"q": "x"}


async def test_dispatch_unknown_tool_emits_structured_error():
    block = await dispatch({"id": "u2", "name": "ghost", "input": {}}, [_spec()], deps=object())
    assert block["is_error"] is True
    body = json.loads(block["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "unknown_tool"
    assert "ghost" in body["error"]["message"]


async def test_dispatch_invalid_arguments_emit_structured_error():
    block = await dispatch({"id": "u3", "name": "t", "input": {"nope": 1}}, [_spec()], deps=object())
    assert block["is_error"] is True
    body = json.loads(block["content"])
    assert body["error"]["type"] == "invalid_arguments"


async def test_dispatch_propagates_failure_via_is_error():
    block = await dispatch({"id": "u4", "name": "t", "input": {"q": "x"}}, [_spec(fn=_bad)], deps=object())
    assert block["is_error"] is True
    body = json.loads(block["content"])
    assert body["ok"] is False
    assert body["error"]["type"] == "X"


async def test_dispatch_raised_exception_becomes_structured_error():
    async def _raises(args: _Args, deps: object) -> ToolResult:
        raise RuntimeError("kaboom")

    block = await dispatch({"id": "u5", "name": "t", "input": {"q": "x"}}, [_spec(fn=_raises)], deps=object())
    assert block["is_error"] is True
    body = json.loads(block["content"])
    assert body["error"]["type"] == "tool_raised"
    assert "RuntimeError" in body["error"]["message"]
