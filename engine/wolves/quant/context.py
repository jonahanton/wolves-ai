from __future__ import annotations

import importlib.metadata
import importlib.util
from typing import Any

from pydantic import BaseModel, Field

from wolves.observability.budget import Caps

# Approved scientific stack the quant agent may use: (import name, distribution).
APPROVED_PACKAGES: list[tuple[str, str]] = [
    ("duckdb", "duckdb"),
    ("polars", "polars"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("statsmodels", "statsmodels"),
    ("sklearn", "scikit-learn"),
    ("matplotlib", "matplotlib"),
    ("plotly", "plotly"),
    ("lifelines", "lifelines"),
    ("pymc", "pymc"),
    ("arviz", "arviz"),
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


class QuantArtifact(BaseModel):
    """The slice of a run artifact the quant prompt needs: identity plus payload."""

    id: str
    kind: str
    summary: str = ""
    file_paths: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class QuantContext(BaseModel):
    query_title: str
    ask: str
    as_of: str
    workspace_dir: str
    available_packages: dict[str, str] = Field(default_factory=dict)
    input_artifacts: list[dict] = Field(default_factory=list)
    # Resource budget (rows is soft guidance; bytes/runtime enforced by the executor).
    max_rows: int = 0
    max_output_bytes: int = 0
    max_runtime_seconds: int = 0


# Cap how many dataset artefacts carry a full schema+sample into the prompt;
# build_quant_context includes every dataset, so a multi-source run would
# otherwise blow the prompt budget. Beyond this, datasets are schema-only.
_MAX_SAMPLED_DATASETS = 4
_MAX_SAMPLE_ROWS = 5


def build_quant_context(
    *,
    query_title: str,
    ask: str,
    as_of: str,
    workspace_dir: str,
    artifacts: list[QuantArtifact],
    caps: Caps,
) -> QuantContext:
    relevant_artifacts = [
        a for a in artifacts if a.kind in ("source", "evidence", "dataset", "model_card", "data_quality")
    ]
    sampled = {a.id for a in [a for a in relevant_artifacts if a.kind == "dataset"][:_MAX_SAMPLED_DATASETS]}
    relevant = [
        {
            "id": a.id,
            "kind": a.kind,
            "summary": a.summary,
            "file_paths": a.file_paths,
            "payload": _trim_payload(a, with_sample=a.id in sampled),
        }
        for a in relevant_artifacts
    ]
    return QuantContext(
        query_title=query_title,
        ask=ask,
        as_of=as_of,
        workspace_dir=workspace_dir,
        available_packages=available_packages(),
        input_artifacts=relevant,
        max_rows=caps.max_quant_rows,
        max_output_bytes=caps.max_quant_bytes,
        max_runtime_seconds=caps.max_quant_runtime_seconds,
    )


def _trim_payload(artifact: QuantArtifact, *, with_sample: bool = False) -> dict:
    """Keep the small, useful bits of an artifact payload for the agent prompt.
    For dataset artefacts, thread the real schema (and, when budget allows, a
    short row sample) so quant writes the exact column names rather than guessing."""
    keep = (
        "url",
        "title",
        "claim",
        "value",
        "as_of",
        "published_at",
        "snippet",
        "cache_key",
        "resolved",
        "row_count",
        "columns",
        "schema",
    )
    out = {k: v for k, v in artifact.payload.items() if k in keep}
    if with_sample:
        sample = artifact.payload.get("sample")
        if isinstance(sample, list) and sample:
            out["sample"] = sample[:_MAX_SAMPLE_ROWS]
    text = artifact.payload.get("text")
    if isinstance(text, str):
        out["text"] = text[:800]
    return out
