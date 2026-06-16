"""The Murphy split is an identity: reliability - resolution + uncertainty
equals the mean Brier of the binary forecast cells it decomposes. Pinned on a
small known set so a future refactor cannot silently break the algebra."""

from __future__ import annotations

from wolves.agent.calibration import OUTCOMES, MatchScore, reliability_resolution


def _score(match_id: str, probs: dict[str, float], outcome: str) -> MatchScore:
    return MatchScore(match_id=match_id, date="2026-06-10", outcome=outcome, model_probs=probs)


def _mean_cell_brier(scores: list[MatchScore]) -> float:
    cells = [
        (score.model_probs.get(outcome, 0.0) - (1.0 if outcome == score.outcome else 0.0)) ** 2
        for score in scores
        for outcome in OUTCOMES
    ]
    return sum(cells) / len(cells)


def test_decomposition_identity_holds_on_a_known_set():
    # Every match shares one forecast triple, so each bin's cells carry an
    # identical forecast value. That is exactly the condition under which the
    # binned Murphy split reconstructs the raw mean Brier with no residual.
    probs = {"home": 0.5, "draw": 0.3, "away": 0.2}
    outcomes = ["home", "home", "draw", "away", "away"]
    scores = [_score(str(i), probs, outcome) for i, outcome in enumerate(outcomes)]

    murphy = reliability_resolution(scores, window=20, bins=10)

    assert murphy is not None
    assert murphy.n == len(scores) * len(OUTCOMES)
    assert murphy.brier == murphy.reliability - murphy.resolution + murphy.uncertainty
    assert abs(murphy.brier - _mean_cell_brier(scores)) < 1e-9


def test_returns_none_without_stored_probabilities():
    bare = [MatchScore(match_id="1", date="2026-06-10", outcome="home")]
    assert reliability_resolution(bare, window=20) is None
