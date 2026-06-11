from __future__ import annotations

import json
from pathlib import Path

from wolves.quant.wolves_quant._state import USAGE_FILENAME, Usage


def test_a_zero_usage_flush_never_erases_earlier_counters(tmp_path: Path):
    first = Usage(queries=2, sims=1)
    first.flush(tmp_path)
    Usage().flush(tmp_path)

    counts = json.loads((tmp_path / USAGE_FILENAME).read_text(encoding="utf-8"))
    assert counts["queries"] == 2
    assert counts["sims"] == 1
