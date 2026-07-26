from __future__ import annotations

import json
from pathlib import Path

import pytest

from wolves.archive.contracts import ArchiveManifest
from wolves.archive.errors import ArchiveExportError
from wolves.archive.export import audit_archive, default_days, export_archive
from wolves.archive.publish import release_digest
from wolves.archive.source import (
    LocalArchiveSource,
    RunRecordSet,
    SourceObject,
    complete_snapshots,
)
from wolves.archive.verify import verify_archive


def test_manifest_hashes_detect_modified_payloads(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    output = tmp_path / "archive"

    manifest = export_archive(LocalArchiveSource(source_root), output=output, days=["2026-06-10"])
    payload = output / manifest.days[0].payload.path
    payload.write_bytes(b"altered")

    with pytest.raises(ArchiveExportError, match="payload digest differs"):
        verify_archive(output, ArchiveManifest.model_validate_json((output / "manifest.json").read_bytes()))


def test_manifest_rejects_an_inconsistent_archive_boundary(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    output = tmp_path / "archive"
    manifest = export_archive(LocalArchiveSource(source_root), output=output, days=["2026-06-10"])

    with pytest.raises(ArchiveExportError, match="archive boundary differs"):
        verify_archive(output, manifest.model_copy(update={"archived_through": "2026-06-11T00:00:00Z"}))


def test_complete_snapshot_rejects_a_missing_sidecar(tmp_path: Path):
    source_root = tmp_path / "source"
    run_id = _write_source_snapshot(source_root, day="2026-06-10")
    (source_root / "snapshots/2026/06/10" / f"{run_id}.pairing-matrices.json").unlink()

    complete, rejected = complete_snapshots(LocalArchiveSource(source_root))

    assert complete == []
    assert "lacks required pairing-matrices sidecar" in next(iter(rejected.values()))
    with pytest.raises(ArchiveExportError, match="incomplete archive sources"):
        export_archive(
            LocalArchiveSource(source_root),
            output=tmp_path / "archive",
            days=["2026-06-10"],
        )


def test_default_days_fill_agent_calendar_gaps_without_extending_for_later_live_snapshots(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-13")
    _write_source_snapshot(source_root, day="2026-06-15")
    _write_source_snapshot(source_root, day="2026-06-16", kind="live")
    complete, _ = complete_snapshots(LocalArchiveSource(source_root))

    assert default_days(complete) == ["2026-06-13", "2026-06-14", "2026-06-15"]


def test_default_days_stop_the_day_after_the_final(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-13")
    _write_source_snapshot(source_root, day="2026-07-21")
    complete, _ = complete_snapshots(LocalArchiveSource(source_root))

    assert default_days(complete)[-1] == "2026-07-20"
    with pytest.raises(ArchiveExportError, match="archive day exceeds"):
        export_archive(
            LocalArchiveSource(source_root),
            output=tmp_path / "archive",
            days=["2026-07-21"],
        )


def test_export_provenance_includes_fixture_metadata_source(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    _write_source_snapshot(source_root, day="2026-06-11")
    live = source_root / "live"
    live.mkdir()
    (live / "results.json").write_text('{"fixtures":[],"results":{}}', encoding="utf-8")

    manifest = export_archive(
        LocalArchiveSource(source_root),
        output=tmp_path / "archive",
        days=["2026-06-11"],
        run_records=RunRecordSet(
            records=[],
            source_object=SourceObject(
                key="dynamodb://runs/RUN",
                body=b'{"runs":[]}',
                version_id=None,
            ),
        ),
    )
    provenance = json.loads((tmp_path / "archive/provenance.json").read_bytes())
    sources = provenance[manifest.days[0].payload.path]

    assert "live/results.json" in {source["key"] for source in sources}
    assert {
        source["key"]
        for source in sources
        if source["key"].endswith(".json") and ".distributions." not in source["key"]
    } >= {
        "snapshots/2026/06/10/agent-20260610-090000.json",
        "snapshots/2026/06/11/agent-20260611-090000.json",
    }
    assert len(sources) == len({(source["key"], source["sha256"]) for source in sources})
    dynamo = next(source for source in sources if source["key"].startswith("dynamodb://"))
    assert (tmp_path / "archive" / dynamo["archive_path"]).read_bytes() == b'{"runs":[]}'


def test_release_digest_covers_provenance(tmp_path: Path):
    root = tmp_path / "archive"
    root.mkdir()
    (root / "manifest.json").write_text("manifest", encoding="utf-8")
    (root / "provenance.json").write_text("first", encoding="utf-8")
    first = release_digest(root)

    (root / "provenance.json").write_text("second", encoding="utf-8")

    assert release_digest(root) != first


def test_audit_classifies_retained_live_history_as_deliberately_omitted(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    history = source_root / "live/history/2026-06-10"
    history.mkdir(parents=True)
    (history / "120000.json").write_text("{}", encoding="utf-8")

    report = audit_archive(LocalArchiveSource(source_root), days=["2026-06-10"])

    assert report.days[0].live_detail == "omitted"
    assert report.days[0].selected_run_id == "agent-20260610-090000"
    assert len(report.days[0].source_keys) == 5


def _write_source_snapshot(root: Path, *, day: str, kind: str = "agent") -> str:
    path_day = day.replace("-", "/")
    directory = root / f"snapshots/{path_day}"
    directory.mkdir(parents=True)
    compact_day = day.replace("-", "")
    run_id = f"{kind}-{compact_day}-090000"
    (directory / f"{run_id}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run": {
                    "run_id": run_id,
                    "created_at": f"{day}T09:00:00Z",
                    "as_of": day,
                    "n_sims": 1,
                    "engine_version": "test",
                    "kind": kind,
                },
                "focus": {
                    "team_id": "england",
                    "group": "A",
                    "finish_probs": {},
                    "reach_probs": {},
                    "paths": [],
                },
                "slots": [],
                "teams": [{"team_id": "england", "name": "England", "group": "A", "elo": 1800}],
            }
        ),
        encoding="utf-8",
    )
    sidecars = {
        "distributions": '{"quantile_levels":[],"provenance":"test","teams":{}}',
        "bracket-samples": '{"samples":[]}',
        "pairing-matrices": '{"rounds":{}}',
        "match-wdl-draws": '{"matches":{}}',
    }
    for name, body in sidecars.items():
        (directory / f"{run_id}.{name}.json").write_text(body, encoding="utf-8")
    return run_id
