from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import SourceRef, ToolError, ToolResult

_MIN_READABLE_CHARS = 80


class WebFetchArgs(BaseModel):
    url: str
    refresh: bool = False


def _empty_page(url: str, chars: int) -> ToolResult[Any]:
    return ToolResult(
        ok=False,
        payload=None,
        error=ToolError(
            type="empty_page",
            message=f"{url} returned no readable text ({chars} chars); do not refetch it, try another source",
        ),
    )


def _from_cache(args: WebFetchArgs, deps: AgentDeps) -> ToolResult[Any] | None:
    if args.refresh or deps.articles is None:
        return None
    cached = deps.articles.get(args.url)
    if cached is None or cached.run_id == deps.runtime.run_id:
        return None
    age = cached.age_hours()
    if age > deps.settings.article_cache_max_age_hours:
        return None
    if deps.source_memory is not None:
        # Cached text is the text this run read; confirmed claims may cite it.
        deps.source_memory.record(args.url, run_id=deps.runtime.run_id, disposition="fetched")
    return ToolResult(
        payload={
            "url": cached.final_url,
            "title": cached.title,
            "text": cached.text,
            "cached": {
                "retrieved_at": cached.retrieved_at,
                "run_id": cached.run_id,
                "age_hours": round(age, 1),
                "notice": "served from the cross-run article cache; pass refresh=true if you need a live copy",
            },
        },
        sources=[SourceRef(url=cached.final_url, title=cached.title or cached.final_url, source_type="web")],
    )


async def _web_fetch(args: WebFetchArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    if deps.source_memory is not None:
        seen = deps.source_memory.seen(args.url)
        if seen is not None:
            if seen.disposition == "empty":
                return _empty_page(args.url, 0)
            if seen.disposition == "fetched" and seen.last_seen_run == deps.runtime.run_id:
                return ToolResult(
                    payload={
                        "url": args.url,
                        "notice": "already fetched this run; its evidence is on the ledger or in a sibling artifact",
                    }
                )
    cached = _from_cache(args, deps)
    if cached is not None:
        return cached
    page = await run_with_timeout(
        deps.web.fetch(actor=deps.actor, url=args.url),
        tool_name="web_fetch",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    disposition = "fetched" if len(page.text.strip()) >= _MIN_READABLE_CHARS else "empty"
    if deps.source_memory is not None:
        deps.source_memory.record(page.final_url, run_id=deps.runtime.run_id, disposition=disposition)
        if page.final_url != args.url:
            # The requested URL is what siblings will cite; the dedupe check must see it too.
            deps.source_memory.record(args.url, run_id=deps.runtime.run_id, disposition=disposition)
    if disposition == "empty":
        return _empty_page(page.final_url, len(page.text.strip()))
    if deps.articles is not None:
        deps.articles.put(
            url=args.url, final_url=page.final_url, title=page.title, text=page.text, run_id=deps.runtime.run_id
        )
    return ToolResult(
        payload={"url": page.final_url, "title": page.title, "text": page.text},
        sources=[SourceRef(url=page.final_url, title=page.title or page.final_url, source_type="web")],
    )


SPEC = ToolSpec(
    name="web_fetch",
    description=(
        "Fetch a URL and return its readable text. Use after rank_relevance has triaged your search "
        "results; fetch only the top-ranked few. Only fetched pages can back a confirmed claim. A page "
        "a recent run already fetched is served from the article cache with its retrieval timestamp "
        "and age; pass refresh=true when the page itself will have changed. A page that yields no "
        "readable text fails; move to another source rather than retrying it."
    ),
    args_model=WebFetchArgs,
    fn=_web_fetch,
)
