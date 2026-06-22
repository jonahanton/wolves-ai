from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.models.anthropic import AnthropicModelSettings

from wolves.agent.deps import AgentDeps
from wolves.agent.relevance_memory import RankedSource
from wolves.agent.sources import source_tier
from wolves.prompts import prompt
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


class Candidate(BaseModel):
    url: str
    title: str
    snippet: str | None = None
    published_at: str | None = None


class RankRelevanceArgs(BaseModel):
    sub_question: str
    candidates: list[Candidate] = Field(min_length=1, max_length=24)

    @model_validator(mode="before")
    @classmethod
    def accept_search_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        candidates = data.get("candidates")
        if isinstance(candidates, dict) and isinstance(candidates.get("hits"), list):
            return {**data, "candidates": candidates["hits"]}
        return data


class _Ranking(BaseModel):
    url: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class _Rankings(BaseModel):
    rankings: list[_Ranking]


_RANKER = Agent(
    output_type=ToolOutput(_Rankings, strict=True),
    system_prompt=prompt("rank_relevance"),
    output_retries=1,
)
_RANK_SETTINGS = AnthropicModelSettings(anthropic_cache="5m", max_tokens=1500)


def _candidate_block(c: Candidate, seen_run: str | None, prior: RankedSource | None) -> str:
    tier = source_tier(c.url)
    parts = [
        f"url: {c.url}",
        f"title: {c.title}",
        f"tier: {tier if tier is not None else 'unknown'}",
        f"published: {c.published_at or 'unknown'}",
    ]
    if c.snippet:
        parts.append(f"snippet: {c.snippet[:300]}")
    if seen_run:
        parts.append(f"already seen in run {seen_run}")
    if prior is not None:
        parts.append(
            f"previously ranked {prior.score:.2f} at {prior.ranked_at} for: {prior.sub_question[:80]} "
            f"({prior.reason[:120]})"
        )
    return "\n".join(parts)


async def _rank_relevance(args: RankRelevanceArgs, deps: AgentDeps) -> ToolResult[Any]:
    memory = deps.source_memory
    seen: dict[str, str | None] = {}
    for c in args.candidates:
        record = (
            memory.seen(c.url, as_of=deps.as_of, current_run_id=deps.runtime.run_id) if memory is not None else None
        )
        seen[c.url] = record.last_seen_run if record is not None else None
    priors = (
        {
            c.url: deps.relevance_memory.latest(c.url, as_of=deps.as_of, current_run_id=deps.runtime.run_id)
            for c in args.candidates
        }
        if deps.relevance_memory
        else {}
    )
    user = f"Sub-question: {args.sub_question}\nAs of: {deps.as_of}\n\nCandidates:\n\n" + "\n\n".join(
        _candidate_block(c, seen.get(c.url), priors.get(c.url)) for c in args.candidates
    )
    try:
        model = deps.relevance_model.for_actor(deps.actor, operation="rank_relevance")
        ranked = (await _RANKER.run(user, model=model, model_settings=_RANK_SETTINGS)).output
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
    for c in args.candidates:
        if c.url not in by_url:
            continue
        if memory is not None:
            memory.record(c.url, run_id=deps.runtime.run_id, disposition="ranked")
        if deps.relevance_memory is not None:
            deps.relevance_memory.record(
                url=c.url,
                sub_question=args.sub_question,
                score=by_url[c.url].score,
                reason=by_url[c.url].reason,
                run_id=deps.runtime.run_id,
            )
    retrieval_id = None
    if deps.artifacts is not None:
        artifact = deps.artifacts.add(
            kind="retrieval",
            created_by=deps.actor,
            summary=f"ranked {len(rankings)} candidates for: {args.sub_question[:70]}",
            payload={"sub_question": args.sub_question, "rankings": rankings},
        )
        retrieval_id = artifact.id
    return ToolResult(payload={"rankings": rankings, "retrieval_id": retrieval_id})


SPEC = ToolSpec(
    name="rank_relevance",
    description=(
        "Rank search candidates against your sub-question in one batched call: each gets a "
        "holistic 0-1 score with a one-line reason, its source tier, whether a previous run "
        "already saw it and any prior ranking with its timestamp, so judgements are not redone. "
        "You may pass candidates directly from web_search's hits payload. "
        "The default research move is broad search, rank, fetch the top few; "
        "you stay free to overrule a ranking with your own stated reason. Costs no fetch budget."
    ),
    args_model=RankRelevanceArgs,
    fn=_rank_relevance,
)
