from __future__ import annotations

import importlib.metadata
import importlib.util
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from wolves.data.store import DatasetStore

if TYPE_CHECKING:
    from wolves.agent.deps import AgentDeps

logger = logging.getLogger(__name__)

# Approved scientific stack the quant agent may use: (import name, distribution).
# Everything listed is a real engine dependency; the sandbox never advertises
# an instrument that fails on import.
APPROVED_PACKAGES: list[tuple[str, str]] = [
    ("duckdb", "duckdb"),
    ("polars", "polars"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("statsmodels", "statsmodels"),
    ("sklearn", "scikit-learn"),
    ("emcee", "emcee"),
    ("matplotlib", "matplotlib"),
]


def available_packages() -> dict[str, str]:
    """Approved packages actually importable in this environment, with versions."""
    found: dict[str, str] = {}
    for import_name, dist in APPROVED_PACKAGES:
        if importlib.util.find_spec(import_name) is not None:
            try:
                found[dist] = importlib.metadata.version(dist)
            except importlib.metadata.PackageNotFoundError:
                found[dist] = "?"
    return found


class ContextArtifact(BaseModel):
    """One run artifact as the sandbox sees it: metadata plus local paths."""

    id: str
    kind: str
    created_by: str
    summary: str
    payload_path: str
    workspace_path: str | None = None


class SandboxContext(BaseModel):
    """Everything `wq` needs to rebuild the run's deterministic surface
    inside the sandbox, written to inputs/context.json once per node."""

    as_of: str
    run_id: str
    focus_team: str
    data_dir: str
    runs_root: str
    dataset_path: str | None = None
    dataset_id: str | None = None
    ledger_path: str | None = None
    calibration_path: str | None = None
    archive_dir: str | None = None
    market_series_available: bool = False
    market_series_latest_at: str | None = None
    current_outrights: dict[str, Any] | None = None
    artifacts: dict[str, ContextArtifact] = Field(default_factory=dict)
    default_n_sims: int = 50_000
    packages: dict[str, str] = Field(default_factory=dict)


def build_sandbox_context(deps: AgentDeps) -> SandboxContext:
    """Assemble the sandbox context from run state; missing pieces stay None
    so a dev run without a dataset still gets a working workbench."""
    settings = deps.settings
    dataset_path: str | None = None
    dataset_id: str | None = None
    try:
        path, manifest = DatasetStore(settings).fetch()
        dataset_path, dataset_id = str(path), manifest.dataset_id
    except Exception as exc:
        logger.warning("sandbox context has no dataset: %s", exc)
    artifacts: dict[str, ContextArtifact] = {}
    if deps.artifacts is not None:
        for record in deps.artifacts.all():
            payload_path = deps.artifacts.payload_path(record.id)
            if payload_path is None:
                continue
            artifacts[record.id] = ContextArtifact(
                id=record.id,
                kind=record.kind,
                created_by=record.created_by,
                summary=record.summary,
                payload_path=payload_path,
                workspace_path=deps.artifacts.workspace_path(record.id),
            )
    calibration = settings.calibration_path
    archive = settings.runs_root / "odds-archive"
    from wolves.markets.series import load_series

    market_series = load_series(archive) if archive.exists() else []
    return SandboxContext(
        as_of=deps.as_of,
        run_id=deps.runtime.run_id,
        focus_team=settings.focus_team,
        data_dir=str(settings.data_dir),
        runs_root=str(settings.runs_root),
        dataset_path=dataset_path,
        dataset_id=dataset_id,
        ledger_path=str(deps.ledger.path) if deps.ledger.path.exists() else None,
        calibration_path=str(calibration) if calibration.exists() else None,
        archive_dir=str(archive) if market_series else None,
        market_series_available=bool(market_series),
        market_series_latest_at=market_series[-1].captured_at if market_series else None,
        current_outrights=deps.market_cache.get("outrights"),
        artifacts=artifacts,
        default_n_sims=settings.n_sims,
        packages=available_packages(),
    )
