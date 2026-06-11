from __future__ import annotations

import json


def access_log_line(
    *, method: str, path: str, status: int, duration_ms: float, client_ip: str, user_agent: str, admin: bool
) -> str:
    """Format one request as a structured JSON log line."""
    record: dict[str, object] = {
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "client_ip": client_ip,
        "user_agent": user_agent,
    }
    if admin:
        record["admin"] = True
    return json.dumps(record)
