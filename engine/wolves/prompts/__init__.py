"""Every prompt and agent-facing guide in the system, one folder, loaded by name."""

from __future__ import annotations

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent


@cache
def prompt(name: str) -> str:
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")
