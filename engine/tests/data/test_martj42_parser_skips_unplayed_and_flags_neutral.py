from __future__ import annotations

from wolves.data.sources.martj42 import parse_results

CSV = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE
2026-03-27,England,Uruguay,1,1,Friendly,London,England,FALSE
2026-06-11,Mexico,South Africa,NA,NA,FIFA World Cup,Mexico City,Mexico,FALSE
"""


def test_played_rows_parse_and_na_scores_are_skipped() -> None:
    records = parse_results(CSV)

    assert [r.home_team for r in records] == ["argentina", "england"]
    final = records[0]
    assert (final.home_goals, final.away_goals) == (3, 3)
    assert final.neutral is True
    assert final.importance == 4.0
    assert records[1].neutral is False
