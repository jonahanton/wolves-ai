"""Static source tier registry: graded context for relevance ranking, never
a deterministic gate. Tier 1 official and wire, tier 2 quality press and
established beat coverage, tier 3 aggregators; unknown domains stay None."""

from __future__ import annotations

from urllib.parse import urlparse

SOURCE_TIERS: dict[str, int] = {
    "fifa.com": 1,
    "uefa.com": 1,
    "conmebol.com": 1,
    "concacaf.com": 1,
    "thefa.com": 1,
    "englandfootball.com": 1,
    "reuters.com": 1,
    "apnews.com": 1,
    "bbc.co.uk": 2,
    "bbc.com": 2,
    "theguardian.com": 2,
    "telegraph.co.uk": 2,
    "thetimes.com": 2,
    "thetimes.co.uk": 2,
    "theathletic.com": 2,
    "skysports.com": 2,
    "espn.com": 2,
    "lequipe.fr": 2,
    "marca.com": 2,
    "as.com": 2,
    "gazzetta.it": 2,
    "kicker.de": 2,
    "ole.com.ar": 2,
    "goal.com": 3,
    "90min.com": 3,
    "givemesport.com": 3,
    "sportbible.com": 3,
    "talksport.com": 3,
    "footballtransfers.com": 3,
    "caughtoffside.com": 3,
}


def source_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def source_tier(url: str) -> int | None:
    domain = source_domain(url)
    while domain:
        tier = SOURCE_TIERS.get(domain)
        if tier is not None:
            return tier
        _, _, domain = domain.partition(".")
    return None
