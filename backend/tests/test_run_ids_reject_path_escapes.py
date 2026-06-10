"""Run and artifact ids interpolate into storage keys resolved against the
local filesystem; an id that smuggles separators or dot segments must fail."""

from __future__ import annotations

import pytest

from wolves_backend.runs import is_safe_id


@pytest.mark.parametrize("value", ["agent-20260610-234149", "rank-relevance-eval", "quant-001", "index"])
def test_real_ids_pass(value):
    assert is_safe_id(value)


@pytest.mark.parametrize("value", ["", "..", ".hidden", "a/b", "a\\b", "../etc", "a" * 101])
def test_escaping_ids_fail(value):
    assert not is_safe_id(value)
