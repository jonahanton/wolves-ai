from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.agent.tools._shared import reserve_or_refuse
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import SourceRef, ToolResult


class WebFetchArgs(BaseModel):
    url: str


async def _web_fetch(args: WebFetchArgs, deps: AgentDeps) -> ToolResult[Any]:
    refused = reserve_or_refuse(deps)
    if refused is not None:
        return refused
    if deps.source_memory is not None:
        seen = deps.source_memory.seen(args.url)
        if seen is not None and seen.last_seen_run == deps.runtime.run_id and seen.disposition == "fetched":
            return ToolResult(
                payload={
                    "url": args.url,
                    "notice": "already fetched this run; its evidence is on the ledger or in a sibling artifact",
                }
            )
    page = await run_with_timeout(
        deps.web.fetch(actor=deps.actor, url=args.url),
        tool_name="web_fetch",
        timeout_seconds=deps.settings.tool_timeout_seconds,
    )
    if deps.source_memory is not None:
        deps.source_memory.record(page.final_url, run_id=deps.runtime.run_id, disposition="fetched")
        if page.final_url != args.url:
            # The requested URL is what siblings will cite; the dedupe check must see it too.
            deps.source_memory.record(args.url, run_id=deps.runtime.run_id, disposition="fetched")
    return ToolResult(
        payload={"url": page.final_url, "title": page.title, "text": page.text},
        sources=[SourceRef(url=page.final_url, title=page.title or page.final_url, source_type="web")],
    )


SPEC = ToolSpec(
    name="web_fetch",
    description=(
        "Fetch a URL and return its readable text. Use after rank_relevance has triaged your search "
        "results; fetch only the top-ranked few. Only fetched pages can back a confirmed claim."
    ),
    args_model=WebFetchArgs,
    fn=_web_fetch,
)
