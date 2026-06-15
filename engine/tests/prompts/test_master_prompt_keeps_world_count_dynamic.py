from __future__ import annotations

from wolves.prompts import prompt


def test_master_prompt_does_not_preserve_world_count_for_continuity():
    text = prompt("master")

    assert "Continuity is not a fixed world count" in text
    assert "Never re-brief a valid registered" in text
    assert "The camp/world count is an output of today's argument" in text
