from __future__ import annotations

import re

_PRIVATE_HANDLE = re.compile(
    r"\b(?:agent|live)-\d{8}-\d{6}\b"
    r"|\brun-\d{8}(?:-\d{6})?\b"
    r"|\b(?:scn-\d{3}|led-\d{4}|"
    r"(?:mixture|evidence|quant|retrieval|draft_forecast|forecast|critique|report)-\d{3})\b"
    r"|\b[a-z]+(?:_[a-z]+)*_\d{4}-\d{2}-\d{2}\b"
)


def private_handles(text: str) -> list[str]:
    return [match.group(0) for match in _PRIVATE_HANDLE.finditer(text)]
