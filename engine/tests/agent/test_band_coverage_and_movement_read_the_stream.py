from __future__ import annotations

import math

import pytest

from wolves.agent.stream import StreamRecord, band_coverage, movement_stats


def _record(run: int, *, mean: float, q10: float | None = None, q90: float | None = None) -> StreamRecord:
    return StreamRecord(
        run_id=f"run-{run}", as_of=f"2026-06-{10 + run:02d}", team="england", mean=mean, q10=q10, q90=q90
    )


def test_coverage_counts_next_means_inside_the_previous_band():
    width = 0.04
    means = [0.10, 0.11, 0.12, 0.13, 0.14, 0.30]
    records = [_record(i, mean=m, q10=m - width, q90=m + width) for i, m in enumerate(means)]
    assert band_coverage(records) == pytest.approx(4 / 5)


def test_coverage_skips_pairs_without_bands_and_empty_stream_is_none():
    records = [_record(0, mean=0.10), _record(1, mean=0.20)]
    assert band_coverage(records) is None
    assert movement_stats([]) is None


def test_movement_ratio_compares_realised_to_band_implied_movement():
    sd = 0.02
    half_band = 1.2816 * sd
    records = [
        _record(0, mean=0.10, q10=0.10 - half_band, q90=0.10 + half_band),
        _record(1, mean=0.13, q10=0.13 - half_band, q90=0.13 + half_band),
        _record(2, mean=0.12, q10=0.12 - half_band, q90=0.12 + half_band),
    ]
    stats = movement_stats(records)
    assert stats is not None
    expected_movement = math.sqrt((0.03**2 + 0.01**2) / 2) * 100.0
    assert stats.movement_pp == pytest.approx(expected_movement, rel=1e-6)
    assert stats.implied_movement_pp == pytest.approx(sd * 100.0, rel=1e-3)
    assert stats.ratio == pytest.approx(expected_movement / (sd * 100.0), rel=1e-3)
