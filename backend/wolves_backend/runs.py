from __future__ import annotations

import json
import re
from collections import Counter

from wolves_backend.models import ArtifactRecord, EventsSummary

# No separators or leading dot, so an id can never escape its run directory
# when storage resolves keys against the local filesystem.
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def is_safe_id(value: str) -> bool:
    return SAFE_ID_PATTERN.fullmatch(value) is not None


def journal_key(run_id: str) -> str:
    return f"runs/{run_id}/journal.md"


def events_key(run_id: str) -> str:
    return f"runs/{run_id}/events.jsonl"


def artifact_index_key(run_id: str) -> str:
    return f"runs/{run_id}/artifacts/index.json"


def artifact_key(run_id: str, artifact_id: str) -> str:
    return f"runs/{run_id}/artifacts/{artifact_id}.json"


def summarise_events(ndjson: str) -> EventsSummary:
    """Reduce an event log to counts per kind and the first and last timestamps."""
    kinds: Counter[str] = Counter()
    timestamps: list[str] = []
    count = 0
    for line in ndjson.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        count += 1
        kinds[str(event.get("kind", "unknown"))] += 1
        if isinstance(event.get("ts"), str):
            timestamps.append(event["ts"])
    return EventsSummary(
        count=count,
        kinds=dict(kinds),
        first_ts=min(timestamps) if timestamps else None,
        last_ts=max(timestamps) if timestamps else None,
    )


def artifact_records(index_json: str) -> list[ArtifactRecord]:
    """Parse a run's artifact index into wire records, tolerating absent fields."""
    try:
        index = json.loads(index_json)
    except ValueError:
        return []
    records = index.get("records") if isinstance(index, dict) else None
    if not isinstance(records, list):
        return []
    return [
        ArtifactRecord(
            id=str(record.get("id", "")),
            kind=str(record.get("kind", "")),
            summary=str(record.get("summary", "")),
            created_at=str(record.get("created_at", "")),
            created_by=str(record.get("created_by", "")),
        )
        for record in records
        if isinstance(record, dict)
    ]
