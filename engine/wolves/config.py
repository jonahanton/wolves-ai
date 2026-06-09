from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed environment settings. Reads `.env` then the process environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    # Cap on SDK-internal retries (default is 2). Bumped because the
    # engine fans out concurrent LLM calls.
    anthropic_max_retries: int = 5
    smart_model: str = "claude-opus-4-8"
    fast_model: str = "claude-sonnet-4-6"
    worker_model: str = "claude-haiku-4-5"

    brave_api_key: str = ""
    exa_api_key: str = ""

    logfire_token: str = ""

    odds_api_key: str = ""
    api_football_key: str = ""
    football_data_api_key: str = ""

    snapshot_dir: Path = Path("snapshots")
    dynamo_endpoint: str = ""

    runs_root: Path = Path("runs")
    tool_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
