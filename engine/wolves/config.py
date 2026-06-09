from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Engine configuration; every knob env-driven with workable defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = REPO_ROOT / "data"
    snapshot_dir: Path = REPO_ROOT / "runs"
    n_sims: int = 10_000
