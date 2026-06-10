from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


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

    data_dir: Path = REPO_ROOT / "data"
    n_sims: int = 10_000

    aws_region: str = "eu-west-2"
    dynamo_endpoint: str = ""
    dynamo_table: str = "wolves-forecaster"
    snapshot_bucket: str = ""
    agent_state_bucket: str = ""
    agent_state_prefix: str = "agent-state"

    runs_root: Path = REPO_ROOT / "runs"
    tool_timeout_seconds: float = 30.0
    tool_result_max_chars: int = 8000

    bookmaker_leg_weight: float = 1.0
    polymarket_leg_weight: float = 1.0

    agent_submit_retries: int = 3
    agent_k_samples: int = 3

    graph_max_waves: int = 4
    graph_max_nodes: int = 12
    graph_max_wave_workers: int = 4
    graph_node_timeout_s: int = 240
    graph_research_request_limit: int = 8
    graph_quant_request_limit: int = 8
    graph_forecast_request_limit: int = 16
    graph_critic_request_limit: int = 4

    confirmed_delta_cap_elo: float = 50.0
    soft_delta_cap_elo: float = 10.0
    justification_threshold: float = 0.05
    tripwire_threshold: float = 0.10
    governor_window: int = 20

    lessons_path: Path = REPO_ROOT / "runs" / "LESSONS.md"
    calibration_path: Path = REPO_ROOT / "runs" / "calibration.jsonl"

    agent_run_ceiling_usd: float = 0.25
    agent_run_ceiling_max_usd: float = 1.50


@lru_cache
def get_settings() -> Settings:
    return Settings()
