from __future__ import annotations

import json
from datetime import UTC, datetime

from wolves_backend.audit import build_audit_item

NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def test_audit_item_contract():
    item = build_audit_item(action="run-now", source_ip="203.0.113.7", payload={"force": False}, now=NOW)
    assert item == {
        "PK": "AUDIT",
        "SK": "2026-06-10T12:00:00+00:00#run-now",
        "action": "run-now",
        "actor": "admin-token",
        "source_ip": "203.0.113.7",
        "payload": json.dumps({"force": False}),
        "ttl": int(NOW.timestamp()) + 180 * 24 * 3600,
    }


def test_missing_client_ip_is_recorded_empty():
    item = build_audit_item(action="stop", source_ip=None, payload={}, now=NOW)
    assert item["source_ip"] == ""
