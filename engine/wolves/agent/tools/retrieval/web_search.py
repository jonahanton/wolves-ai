from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.as_of import future_date_mentions
from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import SourceRef, ToolError, ToolResult

_INTERNAL_ID = re.compile(r"\b(?:scn|led|mixture|evidence|quant)-\d{3}\b|\b[a-z]+_watch_\d{4}-\d{2}-\d{2}\b")


class WebSearchArgs(BaseModel):
    query: str
    provider: Literal["brave", "exa"] | None = None
    count: int = 8
    freshness: str | None = None


async def _web_search(args: WebSearchArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    if _INTERNAL_ID.search(args.query):
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="internal_id_query",
                message="internal run ids are not public search terms; search the named team, player, source or event",
            ),
        )
    if deps.as_of:
        future_dates = future_date_mentions(args.query, as_of=deps.as_of)
        if future_dates:
            return ToolResult(
                ok=False,
                payload=None,
                error=ToolError(
                    type="future_date_query",
                    message=(
                        f"query contains date(s) after today {deps.as_of}: {', '.join(future_dates[:3])}. "
                        "Do not search beyond the forecast as-of date."
                    ),
                ),
            )
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
        "when recency matters. Never include internal ids such as scn-001, led-0001 or mixture-002; "
        "search the underlying team, player, source or event instead."
    ),
    args_model=WebSearchArgs,
    fn=_web_search,
)
