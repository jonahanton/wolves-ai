from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from wolves.data.sources.football_data import parse_workbook


def _workbook(frame: pd.DataFrame, *, header: list[str]) -> bytes:
    buffer = io.BytesIO()
    frame.columns = pd.Index(header)
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def test_duplicate_header_trios_parse_and_incomplete_trios_drop() -> None:
    frame = pd.DataFrame(
        [
            ["World Cup 2014", "Brazil", "Croatia", datetime(2014, 6, 12), 3, 1, 1.25, 6.0, 12.0],
            ["World Cup 2014", "Spain", "Netherlands", datetime(2014, 6, 13), 1, 5, 1.8, None, 4.5],
        ]
    )
    header = ["Competition", "Home", "Away", "Date", "HGFT", "AGFT", "bet365", "bet365.1", "bet365.2"]

    records = parse_workbook(_workbook(frame, header=header))

    assert len(records) == 1
    record = records[0]
    assert (record.home_team, record.away_team) == ("brazil", "croatia")
    assert (record.bookmaker, record.home_price, record.draw_price, record.away_price) == ("bet365", 1.25, 6.0, 12.0)


def test_named_trios_of_the_2018_sheet_parse_with_labels() -> None:
    frame = pd.DataFrame(
        [["World Cup 2018", "Russia", "Saudi Arabia", datetime(2018, 6, 14), 5, 0, 1.7, 3.9, 5.6, 1.75, 4.0, 5.8]]
    )
    base = ["Competition", "Home", "Away", "Date", "HGFT", "AGFT"]
    header = [*base, "Pinny-H", "Pinny-D", "Pinny-A", "H-Avg", "D-Avg", "A-Avg"]

    records = parse_workbook(_workbook(frame, header=header))

    assert {(r.bookmaker, r.home_price) for r in records} == {("Pinnacle", 1.7), ("market-average", 1.75)}
