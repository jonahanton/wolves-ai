from __future__ import annotations

import json
from pathlib import Path

from wolves.config import get_settings
from wolves.markets.series import point_from_snapshot
from wolves.sim.format import load_format

FIXTURES = Path(__file__).parents[2] / "wolves" / "clients" / "odds" / "fixtures"


def _snapshot() -> dict:
    return {
        "captured_at": "2026-06-08T08:00:00+00:00",
        "sources": {
            "odds_outrights": {"payload": json.loads((FIXTURES / "outrights.json").read_text())},
            "odds_h2h": {"payload": json.loads((FIXTURES / "h2h.json").read_text())},
            "polymarket": {"payload": []},
        },
    }


def test_outright_and_h2h_last_updates_extracted() -> None:
    point = point_from_snapshot(_snapshot(), load_format(get_settings().data_dir))

    assert point.outright_updated_oldest == "2026-06-08T06:45:00+00:00"
    assert point.outright_updated_newest == "2026-06-08T07:10:00+00:00"
    assert point.matches
    assert all(m.last_update == "2026-06-08T07:00:00+00:00" for m in point.matches)
