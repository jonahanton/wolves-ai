from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from wolves.agent.deps import AgentDeps
from wolves.agent.sources import source_tier
from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.result import ToolError, ToolResult
from wolves.prompts import prompt


class Candidate(BaseModel):
    url: str
    title: str
    snippet: str | None = None
    published_at: str | None = None


class RankRelevanceArgs(BaseModel):
    sub_question: str
    candidates: list[Candidate] = Field(min_length=1, max_length=24)


class _Ranking(BaseModel):
    url: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class _Rankings(BaseModel):
    rankings: list[_Ranking]


def _candidate_block(c: Candidate, seen_run: str | None) -> str:
    tier = source_tier(c.url)
    parts = [f"url: {c.url}", f"title: {c.title}", f"tier: {tier if tier is not None else 'unknown'}"]
    if c.published_at:
        parts.append(f"published: {c.published_at}")
    if c.snippet:
        parts.append(f"snippet: {c.snippet[:300]}")
    if seen_run:
        parts.append(f"already seen in run {seen_run}")
    return "\n".join(parts)


async def _rank_relevance(args: RankRelevanceArgs, deps: AgentDeps) -> ToolResult[Any]:
    memory = deps.source_memory
    seen: dict[str, str | None] = {}
    for c in args.candidates:
        record = memory.seen(c.url) if memory is not None else None
        seen[c.url] = record.last_seen_run if record is not None else None
    user = f"Sub-question: {args.sub_question}\n\nCandidates:\n\n" + "\n\n".join(
        _candidate_block(c, seen.get(c.url)) for c in args.candidates
    )
    try:
        ranked = await deps.llm.structured(
            prompt_name="rank_relevance",
            actor=deps.actor,
            response_model=_Rankings,
            user=user,
            system=prompt("rank_relevance"),
            max_tokens=1500,
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            payload=None,
            error=ToolError(
                type="ranking_unavailable",
                message=f"ranking failed ({exc}); fall back to your own judgement and fetch fewer, better sources",
            ),
        )
    by_url = {r.url: r for r in ranked.rankings}
    rankings = [
        {
            "url": c.url,
            "title": c.title,
            "tier": source_tier(c.url),
            "score": by_url[c.url].score if c.url in by_url else None,
            "reason": by_url[c.url].reason if c.url in by_url else "(not scored)",
            "seen_in_run": seen.get(c.url),
        }
        for c in args.candidates
    ]
    rankings.sort(key=lambda r: (r["score"] is not None, r["score"] or 0.0), reverse=True)
    if memory is not None:
        for c in args.candidates:
            if c.url in by_url:
                memory.record(c.url, run_id=deps.runtime.run_id, disposition="ranked")
    if deps.artifacts is not None:
        deps.artifacts.add(
            kind="retrieval",
            created_by=deps.actor,
            summary=f"ranked {len(rankings)} candidates for: {args.sub_question[:70]}",
            payload={"sub_question": args.sub_question, "rankings": rankings},
        )
    return ToolResult(payload={"rankings": rankings})


SPEC = ToolSpec(
    name="rank_relevance",
    description=(
        "Rank search candidates against your sub-question in one batched call: each gets a "
        "holistic 0-1 score with a one-line reason, its source tier and whether a previous run "
        "already saw it. The default research move is broad search, rank, fetch the top few; "
        "you stay free to overrule a ranking with your own stated reason. Costs no fetch budget."
    ),
    args_model=RankRelevanceArgs,
    fn=_rank_relevance,
)
