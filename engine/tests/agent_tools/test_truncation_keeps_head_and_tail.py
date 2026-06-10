from __future__ import annotations

from wolves.agent_tools._truncation import truncate_result


def test_short_text_returned_unchanged():
    assert truncate_result("hello", 100) == "hello"


def test_zero_or_negative_cap_disables_truncation():
    assert truncate_result("x" * 500, 0) == "x" * 500
    assert truncate_result("x" * 500, -1) == "x" * 500


def test_truncation_keeps_two_thirds_head_one_third_tail():
    text = "A" * 600 + "B" * 600
    out = truncate_result(text, 300)
    assert len(out) == 300
    head, _, tail = out.partition("[... truncated ...]")
    assert set(head.strip()) == {"A"}
    assert set(tail.strip()) == {"B"}
    assert len(head.strip()) > len(tail.strip())


def test_cap_smaller_than_marker_hard_cuts():
    out = truncate_result("x" * 100, 5)
    assert out == "xxxxx"
