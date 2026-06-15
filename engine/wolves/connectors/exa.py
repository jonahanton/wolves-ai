from __future__ import annotations

from typing import Any

import httpx

from ._dates import freshness_range, parse_date, to_end_iso8601, to_iso8601
from ._http import _raise_for_status, async_retrying
from .contracts import SearchClient, SearchHit, SearchResult

_ENDPOINT = "https://api.exa.ai/search"
_FRESHNESS_DAYS = {"pd": 1, "pw": 7, "pm": 31, "py": 365}


class ExaClient(SearchClient):
    provider = "exa"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        *,
        count: int = 8,
        freshness: str | None = None,
        end_published_date: str | None = None,
        include_text: bool = False,
        include_highlights: bool = False,
        domains: list[str] | None = None,
    ) -> SearchResult:
        body: dict[str, Any] = {
            "query": query,
            "type": "auto",
            "numResults": max(1, min(count, 100)),  # Exa allows 1-100
        }
        # Exa requires a full ISO 8601 instant, not a bare date.
        end_iso = to_end_iso8601(end_published_date) if end_published_date else None
        if end_iso:
            body["endPublishedDate"] = end_iso
        if freshness and end_published_date:
            window = freshness_range(end_published_date, lookback_days=_FRESHNESS_DAYS.get(freshness, 3650)) or ""
            start, _, _end = window.partition("to")
            if start_iso := to_iso8601(start):
                body["startPublishedDate"] = start_iso
        if domains:
            body["includeDomains"] = domains

        if include_text or include_highlights:
            contents: dict[str, Any] = {}
            if include_text:
                contents["text"] = {"maxCharacters": 2000}
            if include_highlights:
                contents["highlights"] = {"numSentences": 3}
            body["contents"] = contents

        headers = {
            "x-api-key": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        data = await self._post(body, headers)
        results = data.get("results") or []
        hits = [self._to_hit(item, i) for i, item in enumerate(r for r in results if r.get("url"))]

        return SearchResult(
            provider=self.provider,
            query=query,
            hits=hits,
            request_id=data.get("requestId") or data.get("request_id"),
            null_result=not hits,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.post(_ENDPOINT, json=body, headers=headers)
                _raise_for_status(response)
                return response.json()
        return {}

    @staticmethod
    def _to_hit(item: dict[str, Any], index: int) -> SearchHit:
        snippet = _snippet(item)
        url = item.get("url") or ""
        return SearchHit(
            provider="exa",
            url=url,
            title=item.get("title") or url,
            snippet=snippet,
            rank=index + 1,
            published_at=parse_date(item.get("publishedDate")),
            score=item.get("score"),
            raw=item,
        )


def _snippet(item: dict[str, Any]) -> str:
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    summary = item.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    highlights = item.get("highlights")
    if isinstance(highlights, list):
        joined = " ".join(h.strip() for h in highlights if isinstance(h, str) and h.strip())
        if joined:
            return joined
    return ""
