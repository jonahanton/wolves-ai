from __future__ import annotations

from typing import Any

import httpx

from ._dates import freshness_range, parse_date
from ._http import _raise_for_status, async_retrying
from .contracts import SearchClient, SearchHit, SearchResult

_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_FRESHNESS_DAYS = {"pd": 1, "pw": 7, "pm": 31, "py": 365}


class BraveClient(SearchClient):
    provider = "brave"

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 20.0,
        country: str = "US",
        extra_snippets: bool = True,
    ) -> None:
        self._api_key = api_key
        self._country = country
        # extra_snippets is a paid-plan feature; allow disabling it for free tiers.
        self._extra_snippets = extra_snippets
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
        params: dict[str, Any] = {
            "q": query,
            "count": max(1, min(count, 20)),  # Brave allows 1-20
            "country": self._country,
            "search_lang": "en",
        }
        if self._extra_snippets:
            params["extra_snippets"] = "true"
        freshness_value = _freshness_value(freshness, end_published_date)
        if freshness_value:
            params["freshness"] = freshness_value

        headers = {
            "X-Subscription-Token": self._api_key,
            "Accept": "application/json",
        }

        data = await self._get(params, headers)
        results = (data.get("web") or {}).get("results") or []
        hits = [self._to_hit(item, i) for i, item in enumerate(results)]

        return SearchResult(
            provider=self.provider,
            query=query,
            hits=hits,
            request_id=data.get("request_id"),
            null_result=not hits,
        )

    async def _get(self, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        async for attempt in async_retrying():
            with attempt:
                response = await self._client.get(_ENDPOINT, params=params, headers=headers)
                _raise_for_status(response)
                return response.json()
        return {}

    @staticmethod
    def _to_hit(item: dict[str, Any], index: int) -> SearchHit:
        parts = [item.get("description") or ""]
        extra = item.get("extra_snippets") or []
        parts.extend(s for s in extra if isinstance(s, str))
        snippet = " ".join(p.strip() for p in parts if p and p.strip())
        published_at = parse_date(item.get("page_age")) or parse_date(item.get("age"))
        return SearchHit(
            provider="brave",
            url=item.get("url") or "",
            title=item.get("title") or item.get("url") or "",
            snippet=snippet,
            rank=index + 1,
            published_at=published_at,
            score=None,
            raw=item,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _freshness_value(freshness: str | None, end_published_date: str | None) -> str | None:
    if end_published_date is None:
        return freshness
    return freshness_range(end_published_date, lookback_days=_FRESHNESS_DAYS.get(freshness or "", 3650))
