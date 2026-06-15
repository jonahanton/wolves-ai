from __future__ import annotations

from wolves.graph.agents import _research_source_issues
from wolves.graph.contracts import LedgerEvidence, ResearchOutput


def test_non_official_lineup_cannot_be_confirmed():
    output = ResearchOutput(
        summary="England line-up reported.",
        evidence=[
            LedgerEvidence(
                claim="England confirms starting XI vs Croatia",
                source_url="https://cryptobriefing.com/england-starting-xi-world-cup-croatia/",
                quote="Here is the full starting XI.",
                status="confirmed",
                mechanism="lineup announcement",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output)


def test_official_lineup_confirmation_is_allowed():
    output = ResearchOutput(
        summary="England line-up confirmed.",
        evidence=[
            LedgerEvidence(
                claim="England confirms starting XI vs Croatia",
                source_url="https://www.fifa.com/en/match-centre/match/17/285023/289273/400021462",
                quote="Line-ups",
                status="confirmed",
                mechanism="lineup announcement",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output) == []


def test_non_lineup_injury_claim_can_be_confirmed_from_news():
    output = ResearchOutput(
        summary="Saka load management note.",
        evidence=[
            LedgerEvidence(
                claim="Bukayo Saka is nursing an Achilles problem",
                source_url="https://www.espn.com/soccer/story/_/id/48701061/england-world-cup-2026",
                quote="Saka is still nursing an Achilles problem.",
                status="confirmed",
                mechanism="injury management",
                team_id="england",
            )
        ],
    )

    assert _research_source_issues(output) == []
