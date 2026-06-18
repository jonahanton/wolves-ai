"""Pin the UI's AGENT_RUN_WINDOWS to the infra agent crons so a schedule change
cannot silently leave the next-run label advertising the wrong time."""

from __future__ import annotations

import re

from wolves_backend.config import REPO_ROOT

TFVARS = (REPO_ROOT / "infra" / "envs" / "prod" / "variables.tf").read_text(encoding="utf-8")
RUN_SCHEDULE_TS = (REPO_ROOT / "web" / "src" / "lib" / "run-schedule.ts").read_text(encoding="utf-8")


def _infra_windows() -> list[tuple[int, int, str | None]]:
    block = re.search(r"agent_schedule_windows.*?default\s*=\s*\[(.*?)\]", TFVARS, re.S)
    assert block, "agent_schedule_windows default not found"
    out: list[tuple[int, int, str | None]] = []
    for entry in re.finditer(r"\{([^}]*)\}", block.group(1)):
        text = entry.group(1)
        cron = re.search(r'cron\((\d+)\s+(\d+)\s', text)
        assert cron, f"cron not parsed from {text!r}"
        end = re.search(r'end\s*=\s*"([^"]+)"', text)
        out.append((int(cron.group(2)), int(cron.group(1)), end.group(1) if end else None))
    return out


def _ts_windows() -> list[tuple[int, int, str | None]]:
    block = re.search(r"AGENT_RUN_WINDOWS.*?=\s*\[(.*?)\];", RUN_SCHEDULE_TS, re.S)
    assert block, "AGENT_RUN_WINDOWS not found"
    out: list[tuple[int, int, str | None]] = []
    for entry in re.finditer(r"\{([^}]*)\}", block.group(1)):
        text = entry.group(1)
        hour = re.search(r"utcHour:\s*(\d+)", text)
        minute = re.search(r"utcMinute:\s*(\d+)", text)
        until = re.search(r'untilIso:\s*"([^"]+)"', text)
        assert hour and minute, f"window not parsed from {text!r}"
        out.append((int(hour.group(1)), int(minute.group(1)), until.group(1) if until else None))
    return out


def test_agent_run_windows_match_infra_crons_in_order() -> None:
    infra = _infra_windows()
    ts = _ts_windows()
    assert [(h, m) for h, m, _ in ts] == [(h, m) for h, m, _ in infra]


def test_agent_run_window_boundaries_cover_the_us_trip() -> None:
    ts = _ts_windows()
    assert [w[2] for w in ts] == ["2026-06-24T00:00:00Z", "2026-07-14T00:00:00Z", None]
    assert ts[1][:2] == (10, 0)
    assert ts[0][:2] == ts[2][:2] == (6, 30)
