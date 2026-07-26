from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import BaseModel

from wolves.archive.contracts import (
    ARCHIVE_SCHEMA_HASH,
    ArchiveDay,
    ArchiveDayPayload,
    ArchivedResult,
    ArchiveForecastPoint,
    ArchiveManifest,
    ArchiveObject,
    ArchiveRun,
    ArchiveRunPayload,
    ArchiveRunRecord,
)

TS_SOURCE = (
    Path(__file__).resolve().parents[3] / "web/src/lib/archive/contracts.ts"
).read_text(encoding="utf-8")


def interface_fields(name: str) -> set[str]:
    marker = f"export interface {name}"
    start = TS_SOURCE.index("{", TS_SOURCE.index(marker))
    depth = 0
    for index in range(start, len(TS_SOURCE)):
        if TS_SOURCE[index] == "{":
            depth += 1
        elif TS_SOURCE[index] == "}":
            depth -= 1
            if depth == 0:
                body = TS_SOURCE[start + 1 : index]
                return set(re.findall(r"^\s{2}([a-z0-9_]+)\??:", body, re.MULTILINE))
    raise AssertionError(f"unterminated TypeScript interface {name}")


@pytest.mark.parametrize(
    "model",
    [
        ArchiveObject,
        ArchiveDay,
        ArchiveRun,
        ArchiveManifest,
        ArchiveRunRecord,
        ArchiveForecastPoint,
        ArchivedResult,
        ArchiveDayPayload,
        ArchiveRunPayload,
    ],
    ids=lambda model: model.__name__,
)
def test_python_archive_fields_exist_in_the_browser_contract(model: type[BaseModel]):
    assert set(model.model_fields) == interface_fields(model.__name__)


def test_archive_schema_identifier_is_a_content_derived_hex_digest():
    assert re.fullmatch(r"[0-9a-f]{64}", ARCHIVE_SCHEMA_HASH)
    assert "ARCHIVE_SCHEMA_VERSION" not in TS_SOURCE
