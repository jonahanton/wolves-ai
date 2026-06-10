from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wolves.quant.wolves_quant._state import SESSION, SandboxContextError, connection, context

if TYPE_CHECKING:
    import pandas as pd


def query(sql: str, params: list[Any] | None = None) -> pd.DataFrame:
    """Run read-only SQL against the research dataset."""
    frame = connection().execute(sql, params or []).fetchdf()
    SESSION.usage.queries += 1
    SESSION.usage.rows += len(frame)
    return frame


def load_matches(*, team: str | None = None, since: str | None = None, last: int | None = None) -> pd.DataFrame:
    """International results, newest first, optionally filtered by team and date."""
    clauses, params = [], []
    if team is not None:
        clauses.append("(home_team = ? OR away_team = ?)")
        params += [team, team]
    if since is not None:
        clauses.append("date >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit = f"LIMIT {int(last)}" if last is not None else ""
    return query(f"SELECT * FROM matches {where} ORDER BY date DESC {limit}", params)


def load_ratings() -> pd.DataFrame:
    """The fitted per-team strengths of the run's frozen champion state."""
    import pandas as pd

    from wolves.quant.wolves_quant._state import forecaster

    state = forecaster().state
    SESSION.usage.queries += 1
    return pd.DataFrame({"team": list(state.teams), "strength": list(state.strengths)})


def load_ledger() -> pd.DataFrame:
    """This run's evidence ledger as a table."""
    return _jsonl_frame(context().ledger_path, missing="ledger")


def load_calibration() -> pd.DataFrame:
    """The cross-run calibration ledger as a table."""
    return _jsonl_frame(context().calibration_path, missing="calibration ledger")


def load_market_series(*, last_points: int | None = None) -> pd.DataFrame:
    """Outright market probabilities over time, one row per (capture, source, team)."""
    import pandas as pd

    from wolves.markets.series import load_series

    ctx = context()
    if ctx.archive_dir is None:
        raise SandboxContextError("odds archive", "no market series without archived snapshots")
    points = load_series(Path(ctx.archive_dir))
    if last_points is not None:
        points = points[-last_points:]
    rows: list[dict[str, Any]] = []
    for point in points:
        for source, outright in (
            ("bookmakers", point.outright_bookmakers),
            ("polymarket", point.outright_polymarket),
        ):
            for team, prob in outright.items():
                rows.append({"captured_at": point.captured_at, "source": source, "team": team, "p_title": prob})
    SESSION.usage.queries += 1
    SESSION.usage.rows += len(rows)
    return pd.DataFrame(rows)


def artifact(artifact_id: str) -> dict[str, Any]:
    """Open a prior node's artifact payload by id."""
    record = context().artifacts.get(artifact_id)
    if record is None:
        known = ", ".join(sorted(context().artifacts)) or "(none)"
        raise SandboxContextError(f"artifact {artifact_id!r}", f"known ids: {known}")
    SESSION.usage.artifact_reads += 1
    payload: dict[str, Any] = json.loads(Path(record.payload_path).read_text(encoding="utf-8"))
    return payload


def artifact_path(artifact_id: str) -> str:
    """Path to a predecessor's workspace directory (its code, inputs and outputs)."""
    record = context().artifacts.get(artifact_id)
    if record is None or record.workspace_path is None:
        raise SandboxContextError(f"workspace for {artifact_id!r}", "only quant artifacts carry a workspace")
    SESSION.usage.artifact_reads += 1
    return record.workspace_path


def _jsonl_frame(path: str | None, *, missing: str) -> pd.DataFrame:
    import pandas as pd

    if path is None:
        raise SandboxContextError(missing, "the run has not produced one yet")
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    SESSION.usage.queries += 1
    SESSION.usage.rows += len(rows)
    return pd.DataFrame(rows)
