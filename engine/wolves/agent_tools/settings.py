from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebFetchSettings:
    user_agent: str = "wolves-agent-tools"
    timeout_seconds: float = 10.0
    total_timeout_seconds: float = 30.0
    pdf_total_timeout_seconds: float = 60.0
    max_redirects: int = 3
    max_bytes: int = 5 * 1024 * 1024
    pdf_max_bytes: int = 25 * 1024 * 1024
    respect_robots: bool = False
