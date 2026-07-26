from __future__ import annotations

import json
from pathlib import Path

import pytest

from wolves.archive.contracts import ArchiveManifest
from wolves.archive.export import ArchiveExportError, audit_archive, default_days, export_archive, verify_archive
from wolves.archive.source import LocalArchiveSource, complete_snapshots


def test_manifest_hashes_detect_modified_payloads(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    output = tmp_path / "archive"

    manifest = export_archive(LocalArchiveSource(source_root), output=output, days=["2026-06-10"])
    payload = output / manifest.days[0].payload.path
    payload.write_bytes(b"altered")

    with pytest.raises(ArchiveExportError, match="payload digest differs"):
        verify_archive(output, ArchiveManifest.model_validate_json((output / "manifest.json").read_bytes()))


def test_complete_snapshot_rejects_a_missing_sidecar(tmp_path: Path):
    source_root = tmp_path / "source"
    run_id = _write_source_snapshot(source_root, day="2026-06-10")
    (source_root / "snapshots/2026/06/10" / f"{run_id}.pairing-matrices.json").unlink()

    complete, rejected = complete_snapshots(LocalArchiveSource(source_root))

    assert complete == []
    assert "lacks required pairing-matrices sidecar" in next(iter(rejected.values()))


def test_default_days_fill_calendar_gaps_between_published_snapshots(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-13")
    _write_source_snapshot(source_root, day="2026-06-15")
    complete, _ = complete_snapshots(LocalArchiveSource(source_root))

    assert default_days(complete) == ["2026-06-13", "2026-06-14", "2026-06-15"]


def test_export_provenance_includes_fixture_metadata_source(tmp_path: Path):
    source_root = tmp_path / "source"
    _write_source_snapshot(source_root, day="2026-06-10")
    live = source_root / "live"
    live.mkdir()
    (live / "results.json").write_text('{"fixtures":[],"results":{}}', encoding="utf-8")

    manifest = export_archive(
        LocalArchiveSource(source_root),
        output=tmp_path / "archive",
        days=["2026-06-10"],
    )
    provenance = json.loads((tmp_path / "archive/provenance.json").read_bytes())
    sources = provenance[manifest.days[0].payload.path]

    assert "live/results.json" in {source["key"] for source in sources}
    assert len(sources) == len({(source["key"], source["sha256"]) for source in sources})


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


def _write_source_snapshot(root: Path, *, day: str) -> str:
    path_day = day.replace("-", "/")
    directory = root / f"snapshots/{path_day}"
    directory.mkdir(parents=True)
    compact_day = day.replace("-", "")
    run_id = f"agent-{compact_day}-090000"
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
                    "kind": "agent",
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
