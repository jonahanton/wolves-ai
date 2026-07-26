from __future__ import annotations

from typing import Any

import pytest

from wolves.archive.source import ArchiveSourceError, S3ArchiveSource


class VersionPaginator:
    def paginate(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {
                "Versions": [
                    {
                        "Key": "snapshots/current.json",
                        "VersionId": "current-version",
                        "IsLatest": True,
                    },
                    {
                        "Key": "snapshots/retired.json",
                        "VersionId": "retired-version",
                        "IsLatest": False,
                    },
                ],
                "DeleteMarkers": [
                    {
                        "Key": "snapshots/retired.json",
                        "IsLatest": True,
                    }
                ],
            }
        ]


class VersionedS3:
    def get_paginator(self, name: str) -> VersionPaginator:
        assert name == "list_object_versions"
        return VersionPaginator()


def test_s3_archive_source_excludes_keys_behind_current_delete_markers():
    source = S3ArchiveSource("archive", client=VersionedS3())

    assert source.list_keys(prefix="snapshots") == ["snapshots/current.json"]
    with pytest.raises(ArchiveSourceError, match="missing source object"):
        source.read("snapshots/retired.json")
