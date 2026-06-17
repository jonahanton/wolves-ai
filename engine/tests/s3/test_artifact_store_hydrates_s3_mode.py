from __future__ import annotations

from wolves.config import Settings
from wolves.s3.artifacts import ArtifactStore


class _FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_bytes(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def list_keys(self, *, prefix: str) -> list[str]:
        return [key for key in sorted(self.objects) if key.startswith(prefix)]


def _store(tmp_path, objects: dict[str, bytes]) -> ArtifactStore:
    store = ArtifactStore(Settings(_env_file=None, runs_root=tmp_path, storage_mode="local"))
    store.mode = "s3"
    store._s3 = _FakeS3(objects)
    return store


def test_s3_mode_get_hydrates_local_file(tmp_path):
    store = _store(tmp_path, {"runs/agent-1/events.jsonl": b"{}\n"})

    body = store.get_bytes("runs/agent-1/events.jsonl", prefer="s3")

    assert body == b"{}\n"
    assert (tmp_path / "runs" / "agent-1" / "events.jsonl").read_bytes() == b"{}\n"


def test_s3_mode_sync_down_hydrates_local_files(tmp_path):
    store = _store(
        tmp_path,
        {
            "runs/agent-1/events.jsonl": b"{}\n",
            "runs/agent-1/ledger.jsonl": b"[]\n",
            "runs/agent-2/events.jsonl": b'{"ok": true}\n',
        },
    )

    count = store.sync_down(prefix="runs/", suffix="/events.jsonl")

    assert count == 2
    assert (tmp_path / "runs" / "agent-1" / "events.jsonl").exists()
    assert (tmp_path / "runs" / "agent-2" / "events.jsonl").exists()


def test_sync_down_can_hydrate_only_workspace_files(tmp_path):
    store = _store(
        tmp_path,
        {
            "runs/agent-1/workspace/quant/quant-1/analysis_001.py": b"result = {'ok': True}\n",
            "runs/agent-1/events.jsonl": b"{}\n",
        },
    )

    count = store.sync_down(prefix="runs/", contains="/workspace/")

    assert count == 1
    assert (tmp_path / "runs" / "agent-1" / "workspace" / "quant" / "quant-1" / "analysis_001.py").exists()
    assert not (tmp_path / "runs" / "agent-1" / "events.jsonl").exists()
