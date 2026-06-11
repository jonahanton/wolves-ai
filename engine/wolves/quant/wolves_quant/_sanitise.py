"""Recursive JSON coercion for the sandbox result contract (the larry pattern)."""

from __future__ import annotations

from typing import Any


def sanitise(obj: Any) -> Any:
    import numpy as np
    import pandas as pd

    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [sanitise(v) for v in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return {"columns": list(obj.columns), "rows": sanitise(obj.head(200).to_numpy())}
    if isinstance(obj, pd.Series):
        return {str(k): sanitise(v) for k, v in obj.head(500).items()}
    if isinstance(obj, dict):
        return {str(k): sanitise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitise(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return sanitise(obj.model_dump())
    return str(obj)
