from __future__ import annotations

from wolves.graph.agents import _research_source_issues, _research_temporal_issues
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


def test_first_party_tool_claims_need_internal_source_urls():
    output = ResearchOutput(
        summary="Markets fetched.",
        evidence=[
            LedgerEvidence(
                claim="England market consensus is 10.3%",
                source_url="https://www.get_odds",
                quote="england: 0.103",
                status="confirmed",
                mechanism="market consensus",
                team_id="england",
            )
        ],
    )

    [issue] = _research_source_issues(output)
    assert "fake web URL" in issue
    assert "internal://get_odds" in issue


def test_future_public_claims_are_rejected_against_as_of_date():
    output = ResearchOutput(
        summary="England full squad trained together on June 16.",
        evidence=[
            LedgerEvidence(
                claim="England full squad trained together on June 16",
                source_url="https://www.standard.co.uk/sport/football/england-team-news.html",
                quote="All of the 26 players were in training on June 16.",
                status="confirmed",
                mechanism="availability",
                team_id="england",
            )
        ],
    )

    issues = _research_temporal_issues(output, "2026-06-14")
    assert issues
    assert "June 16" in " ".join(issues)


def test_internal_tool_timestamps_can_be_after_as_of():
    output = ResearchOutput(
        summary="Odds fetched from the internal market tool.",
        evidence=[
            LedgerEvidence(
                claim="Odds fetched June 15 02:49 UTC",
                source_url="internal://get_odds",
                quote="fetched June 15 02:49 UTC",
                status="confirmed",
                mechanism="market consensus",
                team_id="england",
            )
        ],
    )

    assert _research_temporal_issues(output, "2026-06-14") == []
