from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import SourceRef, ToolResult


class WebSearchArgs(BaseModel):
    query: str
    provider: Literal["brave", "exa"] | None = None
    count: int = 8
    freshness: str | None = None


async def _web_search(args: WebSearchArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    result = await run_with_timeout(
        deps.web.search(
            actor=deps.actor,
            query=args.query,
            provider=args.provider,
            count=args.count,
            freshness=args.freshness,
        ),
        tool_name="web_search",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    hits = [
        {
            "url": h.url,
            "title": h.title,
            "snippet": h.snippet,
            "published_at": h.published_at.isoformat() if h.published_at else None,
        }
        for h in result.hits
    ]
    sources = [SourceRef(url=h.url, title=h.title, source_type="web", snippet=h.snippet[:200]) for h in result.hits]
    return ToolResult(payload={"provider": result.provider, "hits": hits}, sources=sources)


SPEC = ToolSpec(
    name="web_search",
    description=(
        "Search the web. Use Exa for semantic source-finding and Brave for fresh news; "
        "leave provider unset to use whichever is available. Set freshness (e.g. 'pd', 'pw') "
        "when recency matters."
    ),
    args_model=WebSearchArgs,
    fn=_web_search,
)
