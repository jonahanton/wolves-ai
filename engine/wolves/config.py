from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from wolves.s3.layout import BUCKET_DEV, CALIBRATION, LESSONS, StorageMode

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
    worker_model: str = "claude-sonnet-4-6"
    # Empty string means inherit worker_model. Research and critic are
    # extraction-shaped and run fine on the cheap tier; quant and forecast
    # carry the numerical judgement and stay on the worker default.
    graph_research_model: str = "claude-haiku-4-5"
    graph_quant_model: str = ""
    graph_forecast_model: str = ""
    graph_critic_model: str = "claude-haiku-4-5"

    brave_api_key: str = ""
    exa_api_key: str = ""

    logfire_token: str = ""

    odds_api_key: str = ""
    api_football_key: str = ""

    data_dir: Path = REPO_ROOT / "data"
    focus_team: str = "england"
    n_sims: int = 10_000

    aws_region: str = "eu-west-2"
    dynamo_endpoint: str = ""
    dynamo_table: str = "wolves-forecaster"
    bucket: str = BUCKET_DEV
    storage_mode: StorageMode = "both"

    runs_root: Path = REPO_ROOT / "runs"
    tool_timeout_seconds: float = 30.0
    tool_result_max_chars: int = 8000

    bookmaker_leg_weight: float = 1.0
    polymarket_leg_weight: float = 1.0

    agent_submit_retries: int = 3

    graph_max_waves: int = 8
    graph_max_nodes: int = 16
    graph_max_wave_workers: int = 5
    graph_max_research_nodes: int = 6
    graph_max_quant_nodes: int = 6
    graph_max_forecast_nodes: int = 3
    graph_max_critic_nodes: int = 3
    graph_research_timeout_s: int = 300
    graph_quant_timeout_s: int = 1800
    graph_forecast_timeout_s: int = 600
    graph_critic_timeout_s: int = 180
    graph_research_request_limit: int = 32
    graph_quant_request_limit: int = 48
    graph_forecast_request_limit: int = 24
    graph_critic_request_limit: int = 8
    graph_research_tool_budget: int = 20
    graph_quant_tool_budget: int = 24
    graph_forecast_tool_budget: int = 16
    graph_critic_tool_budget: int = 6

    market_movement_noise_floor_pp: float = 0.7

    escalation_threshold_pp: float = 2.0
    escalation_reference_p: float = 0.10
    governor_window: int = 20
    governor_shrink_weight: float = 0.5
    extremising_d: float = 1.0
    scenario_lifecycle_enforcement: str = "soft"
    agent_evening_debrief: bool = False

    agent_run_ceiling_usd: float = 3.00
    agent_run_ceiling_max_usd: float = 5.00
    graph_forecast_reserve_usd: float = 0.35
    graph_forecast_reserve_llm_calls: int = 8

    @property
    def lessons_path(self) -> Path:
        return self.runs_root / LESSONS.key()

    @property
    def calibration_path(self) -> Path:
        return self.runs_root / CALIBRATION.key()


@lru_cache
def get_settings() -> Settings:
    return Settings()
