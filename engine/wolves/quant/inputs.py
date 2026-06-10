"""One-off workspace inputs: the overlay DB and the generated data card.

Built host-side when a node's first run_python call ships the context, so
the sandbox opens tables and documentation without network or rebuild."""

from __future__ import annotations

import logging
from pathlib import Path

from wolves.quant.context import SandboxContext
from wolves.quant.workspace import QuantWorkspace

logger = logging.getLogger(__name__)

OVERLAY_FILENAME = "overlay.duckdb"
DATA_CARD_FILENAME = "data_card.md"
FIELD_GUIDE_FILENAME = "field_guide.md"
_FIELD_GUIDE_SOURCE = Path(__file__).resolve().parents[1] / "agent" / "guides" / "field_guide.md"

_EXAMPLE_QUERIES = {
    "matches": "SELECT date, home_team, away_team, home_goals, away_goals FROM matches "
    "WHERE home_team = 'england' OR away_team = 'england' ORDER BY date DESC LIMIT 10",
    "market_closes": "SELECT * FROM market_closes WHERE tournament = 'wc2022' LIMIT 5",
    "elo_history": "SELECT * FROM elo_history WHERE team = 'england' ORDER BY year",
}


def prepare_inputs(workspace: QuantWorkspace, context: SandboxContext) -> None:
    """Idempotent: builds overlay.duckdb and data_card.md once per node."""
    overlay = workspace.inputs / OVERLAY_FILENAME
    if not overlay.exists():
        _build_overlay(overlay, context)
    card = workspace.inputs / DATA_CARD_FILENAME
    if not card.exists() and context.dataset_path is not None:
        workspace.write(DATA_CARD_FILENAME, render_data_card(context), in_inputs=True)
    guide = workspace.inputs / FIELD_GUIDE_FILENAME
    if not guide.exists():
        workspace.write(FIELD_GUIDE_FILENAME, _FIELD_GUIDE_SOURCE.read_text(encoding="utf-8"), in_inputs=True)


def _build_overlay(destination: Path, context: SandboxContext) -> None:
    """Run-local state as queryable tables: ledger, calibration, market series.

    Built whole or not at all: a partial file would satisfy the idempotence
    check forever, so failures remove it."""
    import duckdb

    con = duckdb.connect(str(destination))
    try:
        built: list[str] = []
        for table, path in (("ledger", context.ledger_path), ("calibration", context.calibration_path)):
            if path is not None and Path(path).exists():
                con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_json_auto(?)", [path])
                built.append(table)
        if context.archive_dir is not None:
            from wolves.markets.series import compact_series

            parquet = compact_series(Path(context.archive_dir))
            con.execute("CREATE TABLE market_series AS SELECT * FROM read_parquet(?)", [str(parquet)])
            built.append("market_series")
        logger.info("overlay db built with tables: %s", ", ".join(built) or "(none)")
    except BaseException:
        con.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        con.close()


def render_data_card(context: SandboxContext) -> str:
    """Schema, counts and example queries straight from the dataset; never hand-maintained."""
    import duckdb

    con = duckdb.connect(context.dataset_path, read_only=True)
    try:
        lines = [
            "# Data card",
            "",
            f"Research dataset `{context.dataset_id}` (read-only, preloaded behind `wq.query`).",
            "The overlay DB (`inputs/overlay.duckdb`) adds run-local tables: ledger, calibration,",
            "market_series; attach is automatic, query them by name.",
            "",
        ]
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for table in tables:
            count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            schema = con.execute(f"DESCRIBE {table}").fetchall()
            columns = ", ".join(f"{name} {dtype}" for name, dtype, *_ in schema)
            lines.append(f"## {table} ({count:,} rows)")
            lines.append(f"Columns: {columns}")
            if table == "matches":
                lo, hi = con.execute("SELECT min(date), max(date) FROM matches").fetchone()
                lines.append(f"Coverage: {lo} to {hi}.")
            example = _EXAMPLE_QUERIES.get(table)
            if example:
                lines.append(f"Example: `{example}`")
            lines.append("")
        return "\n".join(lines)
    finally:
        con.close()
