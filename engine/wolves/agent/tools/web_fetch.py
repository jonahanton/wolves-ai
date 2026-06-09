from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import SourceRef, ToolResult
from wolves.tools._timeout import run_with_timeout


class WebFetchArgs(BaseModel):
    url: str


async def _web_fetch(args: WebFetchArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    page = await run_with_timeout(
        deps.web.fetch(actor=deps.actor, url=args.url),
        tool_name="web_fetch",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    return ToolResult(
        payload={"url": page.final_url, "title": page.title, "text": page.text},
        sources=[SourceRef(url=page.final_url, title=page.title or page.final_url, source_type="web")],
    )


SPEC = ToolSpec(
    name="web_fetch",
    description="Fetch a URL and return its readable text. Use after web_search to read a promising source in full.",
    args_model=WebFetchArgs,
    fn=_web_fetch,
)
