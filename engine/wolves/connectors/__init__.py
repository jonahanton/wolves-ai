from __future__ import annotations

import httpx

from wolves.config import Settings
from wolves.observability.runtime import ObservedRuntime

from .brave import BraveClient
from .contracts import (
    FetchClient,
    FetchedPage,
    SearchClient,
    SearchHit,
    SearchResult,
)
from .exa import ExaClient
from .fakes import FakeFetchClient, FakeSearchClient
from .fetch import HttpFetchClient
from .observed import ObservedWeb


def build_web(
    settings: Settings,
    runtime: ObservedRuntime,
    *,
    client: httpx.AsyncClient | None = None,
) -> ObservedWeb:
    """Build the observed web capability from whichever provider keys are set."""
    brave = BraveClient(settings.brave_api_key, client=client) if settings.brave_api_key else None
    exa = ExaClient(settings.exa_api_key, client=client) if settings.exa_api_key else None
    fetch = HttpFetchClient(client=client)
    return ObservedWeb(runtime=runtime, brave=brave, exa=exa, fetch=fetch)


__all__ = [
    "BraveClient",
    "ExaClient",
    "FakeFetchClient",
    "FakeSearchClient",
    "FetchClient",
    "FetchedPage",
    "HttpFetchClient",
    "ObservedWeb",
    "SearchClient",
    "SearchHit",
    "SearchResult",
    "build_web",
]
