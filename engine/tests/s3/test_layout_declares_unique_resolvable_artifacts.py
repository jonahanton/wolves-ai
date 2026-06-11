from __future__ import annotations

import string

import pytest

from wolves.s3.layout import LAYOUT, SNAPSHOT, UnknownArtifactError, artifact, describe


def test_names_are_unique_and_lookup_resolves():
    assert len({spec.name for spec in LAYOUT}) == len(LAYOUT)
    assert artifact("snapshot") is SNAPSHOT
    with pytest.raises(UnknownArtifactError):
        artifact("nope")


def test_keys_resolve_and_stay_under_their_prefix():
    parts = {
        "date": "2026/06/17",
        "run_id": "run-1",
        "time": "120000",
        "dataset_id": "abc",
        "tournament": "wc2022",
        "snapshot": "outrights",
        "artifact_id": "quant-001",
        "path": "quant/node-1/analysis_001.py",
        "url_sha": "a3f9c2d4e5b60718",
    }
    for spec in LAYOUT:
        fields = [field for _, field, _, _ in string.Formatter().parse(spec.pattern) if field]
        key = spec.key(**{f: parts[f] for f in fields})
        assert key.startswith(spec.prefix)
        assert "{" not in key


def test_mutable_pointers_read_bucket_first():
    for spec in LAYOUT:
        assert spec.prefer == ("s3" if spec.mutable else "local")


def test_describe_covers_every_artifact():
    text = describe()
    assert all(spec.pattern in text for spec in LAYOUT)
