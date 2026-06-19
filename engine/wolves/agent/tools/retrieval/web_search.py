from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.agent.tools.retrieval.query_guard import private_handles
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import SourceRef, ToolError, ToolResult


class WebSearchArgs(BaseModel):
    query: str
    provider: Literal["brave", "exa"] | None = None
    count: int = 8
    freshness: str | None = None
    end_published_date: str | None = None


async def _web_search(args: WebSearchArgs, deps: AgentDeps) -> ToolResult[Any]:
    handles = private_handles(args.query)
    if handles:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="internal_id_query",
                message=(
                    "internal run ids are not public search terms; search the named team, player, source or event "
                    f"instead of {', '.join(handles[:4])}"
                ),
            ),
        )
    end_published_date = _bounded_end_date(args.end_published_date, deps.as_of)
    if isinstance(end_published_date, ToolResult):
        return end_published_date
    provider = args.provider
    if provider == "exa" and provider not in deps.web.providers and "brave" in deps.web.providers:
        provider = "brave"
    if provider is not None and provider not in deps.web.providers:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="search_provider_unavailable",
                message=(
                    f"search provider {args.provider!r} is not configured for this run; available providers: "
                    f"{', '.join(deps.web.providers) or 'none'}"
                ),
            ),
        )
    refused = reserve_or_refuse(deps, keep_free=deps.settings.graph_research_fetch_floor)
    if refused is not None:
        return refused
    result = await run_with_timeout(
        deps.web.search(
            actor=deps.actor,
            query=args.query,
            provider=provider,
            count=args.count,
            freshness=args.freshness,
            end_published_date=end_published_date,
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
    return ToolResult(
        payload={"provider": result.provider, "requested_provider": args.provider, "hits": hits},
        sources=sources,
    )


def _bounded_end_date(requested: str | None, as_of: str) -> str | ToolResult[Any] | None:
    requested_day: date | None = None
    if requested is not None:
        try:
            requested_day = date.fromisoformat(requested.split("T", 1)[0])
        except ValueError:
            return ToolResult(
                ok=False,
                payload=None,
                error=ToolError(type="invalid_arguments", message="end_published_date must be an ISO date"),
            )
    if not as_of:
        return requested_day.isoformat() if requested_day is not None else None
    try:
        as_of_day = date.fromisoformat(as_of)
    except ValueError:
        return requested
    if requested_day is None:
        return as_of
    return min(requested_day, as_of_day).isoformat()


SPEC = ToolSpec(
    name="web_search",
    description=(
        "Search the web. Use Exa for semantic source-finding and Brave for fresh news; "
        "leave provider unset to use whichever is available. Set freshness (e.g. 'pd', 'pw') "
        "when recency matters. Search defaults to the run's as_of date as its latest publish date; override "
        "end_published_date only to make that boundary stricter. Never include internal ids such as scn-001, "
        "led-0001, retrieval-001, mixture-002, draft_forecast-001 or agent-20260613-140248; search the "
        "underlying team, player, source or event instead."
    ),
    args_model=WebSearchArgs,
    fn=_web_search,
)
