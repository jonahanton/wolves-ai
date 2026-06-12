from __future__ import annotations

import pytest

from wolves.agent.stream import StreamRecord, dispersion_scale


def _stream(*, pairs: int, inside: int) -> list[StreamRecord]:
    records: list[StreamRecord] = []
    for i in range(pairs + 1):
        mean = 0.10 if i <= inside else 0.50
        records.append(
            StreamRecord(
                run_id=f"run-{i}", as_of=f"2026-06-{10 + i:02d}", team="england", mean=mean, q10=0.08, q90=0.12
            )
        )
    return records


@pytest.mark.parametrize(
    ("pairs", "inside", "expected"),
    [
        (10, 2, 1.0),
        (25, 10, 1.25),
        (25, 25, 1.0),
    ],
)
def test_widening_requires_min_n_pairs_and_materially_low_coverage(pairs, inside, expected):
    assert dispersion_scale(_stream(pairs=pairs, inside=inside), min_n=20) == expected
