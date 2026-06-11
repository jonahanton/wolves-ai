from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

AUDIT_PK = "AUDIT"
AUDIT_TTL_DAYS = 180


def build_audit_item(
    *, action: str, source_ip: str | None, payload: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    """Build the DynamoDB item recording one admin mutation."""
    at = now or datetime.now(UTC)
    return {
        "PK": AUDIT_PK,
        "SK": f"{at.isoformat()}#{action}",
        "action": action,
        "actor": "admin-token",
        "source_ip": source_ip or "",
        "payload": json.dumps(payload),
        "ttl": int((at + timedelta(days=AUDIT_TTL_DAYS)).timestamp()),
    }
