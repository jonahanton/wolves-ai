"""Pydantic-AI adapter: mount ``ToolSpec``s onto an ``Agent``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import RunContext, Tool
from pydantic_ai.toolsets import FunctionToolset

from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult

BeforeInvokeHook = Callable[[ToolSpec, Any, RunContext[Any]], Awaitable[Any | None]]
AfterResultHook = Callable[[ToolSpec, Any, RunContext[Any], ToolResult], Awaitable[Any]]
PrepareFor = Callable[[ToolSpec], Any | None]


async def _default_after_result(spec: ToolSpec, args: Any, ctx: RunContext[Any], result: ToolResult) -> str:
    return result.model_dump_json()


def _emit_tool_call(deps: Any, tool: str, result: ToolResult) -> None:
    """One uniform event per tool call; run audits census from these."""
    runtime = getattr(deps, "runtime", None)
    actor = getattr(deps, "actor", "unknown")
    if runtime is None:
        return
    message = f"{tool} {'ok' if result.ok else 'error'}"
    if not result.ok and result.error is not None:
        message += f": {result.error.message[:80]}"
    runtime.emit("tool_call", actor, message, tool=tool, ok=result.ok)


def build_toolset(
    specs: list[ToolSpec],
    *,
    before_invoke: BeforeInvokeHook | None = None,
    after_result: AfterResultHook | None = None,
    prepare_for: PrepareFor | None = None,
) -> FunctionToolset:
    """Build a ``FunctionToolset`` containing the specs.

    Pass it via ``Agent(toolsets=[...])`` at construction time.

    ``prepare_for`` is an optional ``(spec) -> ToolPrepareFunc | None``
    callback (per pydantic-ai's ``Tool.prepare`` contract) deciding
    whether the tool is advertised on a given turn.
    """
    after = after_result or _default_after_result
    toolset: FunctionToolset = FunctionToolset()
    for spec in specs:
        toolset.add_tool(_build_tool(spec, before_invoke, after, prepare_for))
    return toolset


def _build_tool(
    spec: ToolSpec,
    before_invoke: BeforeInvokeHook | None,
    after_result: AfterResultHook,
    prepare_for: PrepareFor | None,
) -> Tool:
    async def _runner(ctx: RunContext[Any], **kwargs: Any) -> Any:
        args = spec.args_model(**kwargs)
        if before_invoke is not None:
            short_circuit = await before_invoke(spec, args, ctx)
            if short_circuit is not None:
                return short_circuit
        try:
            result = await spec.fn(args, ctx.deps)
        except Exception as exc:
            # A failing tool is information for the model, not a node death: a
            # bad team id or an upstream 403 comes back as an error the model
            # can correct or work around within its remaining turns.
            result = ToolResult(
                ok=False, payload=None, error=ToolError(type=type(exc).__name__, message=str(exc)[:500])
            )
        _emit_tool_call(ctx.deps, spec.name, result)
        return await after_result(spec, args, ctx, result)

    tool = Tool.from_schema(
        function=_runner,
        name=spec.name,
        description=spec.description,
        json_schema=spec.json_schema,
        takes_ctx=True,
    )
    if prepare_for is not None:
        tool.prepare = prepare_for(spec)
    return tool
