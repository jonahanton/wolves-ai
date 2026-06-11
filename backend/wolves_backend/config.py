from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed environment settings. Reads `.env` then the process environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    aws_region: str = "eu-west-2"
    bucket: str = ""
    storage_dir: Path = REPO_ROOT / "runs"

    dynamo_table: str = "wolves-forecaster"
    dynamo_endpoint: str = ""

    schedule_name: str = "wolves-daily-run"

    ecs_cluster_arn: str = ""
    ecs_task_definition: str = "wolves-engine-daily"
    ecs_subnets: str = ""
    ecs_security_group: str = ""

    admin_token: str = ""
    run_history_limit: int = 50

    @property
    def subnet_ids(self) -> list[str]:
        return [subnet for subnet in self.ecs_subnets.split(",") if subnet]


@lru_cache
def get_settings() -> Settings:
    return Settings()
