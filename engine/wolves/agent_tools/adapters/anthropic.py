"""Native Anthropic SDK adapter: render specs + dispatch tool_use."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.errors import ToolDispatchError
from wolves.agent_tools.result import ToolError, ToolResult

DepsFactory = Callable[[ToolSpec], Any]
AfterResultHook = Callable[[ToolSpec, Any, ToolResult], Awaitable[str]]


async def _default_after_result(spec: ToolSpec, args: Any, result: ToolResult) -> str:
    return result.model_dump_json()


def to_anthropic_tools(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    """Render specs as Anthropic ``ToolParam`` dicts.

    Includes any keys in ``spec.extras`` (e.g. ``cache_control``) so a
    caller can opt into prompt-caching the tool definitions without
    plumbing that knob through every spec.
    """
    out: list[dict[str, Any]] = []
    for spec in specs:
        param: dict[str, Any] = {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.json_schema,
        }
        if spec.extras:
            param.update(spec.extras)
        out.append(param)
    return out


async def dispatch(
    tool_use: dict[str, Any],
    specs: list[ToolSpec],
    deps: Any | DepsFactory,
    *,
    after_result: AfterResultHook | None = None,
) -> dict[str, Any]:
    """Dispatch one ``tool_use`` content block to the matching spec.

    Returns the corresponding ``tool_result`` content block ready to
    splice into the next assistant message:

        {
            "type": "tool_result",
            "tool_use_id": <id from tool_use>,
            "content": <JSON-dumped ToolResult or hook output>,
        }

    On error the result block carries ``"is_error": True`` and a short
    text error.

    ``deps`` may be a single object or a callable ``(spec) -> deps`` so
    different tools can read from different per-tool deps containers.
    """
    name = tool_use.get("name") or ""
    tool_use_id = tool_use.get("id") or ""
    raw_input = tool_use.get("input") or {}

    spec = next((s for s in specs if s.name == name), None)
    if spec is None:
        return _result_block(
            tool_use_id,
            ToolResult(
                ok=False,
                payload=None,
                error=ToolError(type="unknown_tool", message=f"Unknown tool: {name!r}"),
            ),
        )

    try:
        args = spec.args_model(**raw_input)
    except Exception as exc:
        return _result_block(
            tool_use_id,
            ToolResult(
                ok=False,
                payload=None,
                error=ToolError(
                    type="invalid_arguments",
                    message=f"Invalid arguments for {name!r}: {exc}",
                ),
            ),
        )

    try:
        spec_deps = deps(spec) if callable(deps) else deps
    except Exception as exc:
        raise ToolDispatchError(f"Failed to resolve deps for {name!r}: {exc}") from exc

    try:
        result = await spec.fn(args, spec_deps)
    except Exception as exc:
        result = ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="tool_raised",
                message=f"{name!r} raised: {type(exc).__name__}: {exc}",
            ),
        )

    after = after_result or _default_after_result
    content = await after(spec, args, result)
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
        "is_error": not result.ok,
    }


def _result_block(tool_use_id: str, result: ToolResult) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result.model_dump_json(),
        "is_error": not result.ok,
    }
