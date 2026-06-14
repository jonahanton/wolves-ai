"""Lazy sandbox session state: context, usage counters, cached engine surfaces.

Module-level because the sandbox process is single-use: one analysis script,
one context, then exit. Nothing here is shared across calls."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wolves.quant.context import SandboxContext

if TYPE_CHECKING:
    import duckdb

    from wolves.forecast import Forecaster

CONTEXT_FILENAME = "inputs/context.json"
USAGE_FILENAME = "outputs/_usage.json"


class SandboxContextError(Exception):
    def __init__(self, missing: str, hint: str) -> None:
        self.missing = missing
        super().__init__(f"the sandbox context has no {missing}; {hint}")


@dataclass
class Usage:
    queries: int = 0
    rows: int = 0
    sims: int = 0
    artifact_reads: int = 0

    def flush(self, root: Path) -> None:
        # Every script runs in a fresh process, so the file carries the node's
        # cumulative counters; overwriting let a final assemble-only script
        # zero the record and falsely flag the node as quant_no_computation.
        path = root / USAGE_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        counts = dict(self.__dict__)
        if path.exists():
            for key, value in json.loads(path.read_text(encoding="utf-8")).items():
                counts[key] = counts.get(key, 0) + int(value)
        path.write_text(json.dumps(counts), encoding="utf-8")


@dataclass
class Session:
    context: SandboxContext | None = None
    usage: Usage = field(default_factory=Usage)
    forecaster: Forecaster | None = None
    db: duckdb.DuckDBPyConnection | None = None
    baselines: dict[tuple[int, int], dict[str, float]] = field(default_factory=dict)
    root: Path = field(default_factory=Path.cwd)


SESSION = Session()


def context() -> SandboxContext:
    if SESSION.context is None:
        path = SESSION.root / CONTEXT_FILENAME
        if not path.exists():
            raise SandboxContextError("context.json", "run_python writes it; check the workspace inputs/ directory")
        SESSION.context = SandboxContext.model_validate_json(path.read_text(encoding="utf-8"))
    return SESSION.context


def forecaster() -> Forecaster:
    """The run's deterministic surface, rebuilt from the frozen context;
    same dataset + as_of means the identical fitted state as the host."""
    if SESSION.forecaster is None:
        ctx = context()
        if ctx.dataset_path is None:
            raise SandboxContextError("dataset", "simulation helpers need the research dataset")
        from wolves.config import Settings
        from wolves.forecast import Forecaster
        from wolves.models.contracts import DatasetHandle

        settings = Settings(
            _env_file=None,
            data_dir=Path(ctx.data_dir),
            runs_root=Path(ctx.runs_root),
            storage_mode="local",
        )
        handle = DatasetHandle(path=Path(ctx.dataset_path), dataset_id=ctx.dataset_id or "unknown")
        fc = Forecaster(settings, dataset=handle)
        from wolves.sim.results_store import persisted_results, played_match_records

        fc.set_default_results(persisted_results(settings))
        fc.fit(as_of=date.fromisoformat(ctx.as_of), extra_results=played_match_records(settings))
        SESSION.forecaster = fc
    return SESSION.forecaster


def connection() -> duckdb.DuckDBPyConnection:
    if SESSION.db is None:
        ctx = context()
        if ctx.dataset_path is None:
            raise SandboxContextError("dataset", "query helpers need the research dataset")
        import duckdb

        # An in-memory catalog of views over the attached read-only databases,
        # so research and overlay tables both resolve by bare name.
        db = duckdb.connect()
        db.execute(f"ATTACH '{Path(ctx.dataset_path).as_posix()}' AS research (READ_ONLY)")
        catalogs = ["research"]
        overlay = SESSION.root / "inputs" / "overlay.duckdb"
        if overlay.exists():
            db.execute(f"ATTACH '{overlay.as_posix()}' AS overlay (READ_ONLY)")
            catalogs.append("overlay")
        for catalog in catalogs:
            tables = db.execute(f"SELECT table_name FROM duckdb_tables() WHERE database_name = '{catalog}'").fetchall()
            for (table,) in tables:
                db.execute(f'CREATE VIEW IF NOT EXISTS "{table}" AS SELECT * FROM {catalog}."{table}"')
        SESSION.db = db
    return SESSION.db


def finalise() -> None:
    """Write the usage counters; the runner calls this in a finally block."""
    SESSION.usage.flush(SESSION.root)


def read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
