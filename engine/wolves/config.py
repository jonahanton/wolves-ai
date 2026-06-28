from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

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
    # App-level backoff covering deadline-driven timeouts the SDK retries miss.
    llm_request_max_retries: int = 2
    llm_retry_base_delay_s: float = 1.0
    llm_retry_max_delay_s: float = 20.0
    llm_request_timeout_s: float = 120.0
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
    # Master plans visibly better on Opus for ~$0.30 a run; empty inherits fast_model.
    graph_master_model: str = "claude-opus-4-8"
    graph_referee_enabled: bool = True
    graph_referee_model: str = ""
    graph_referee_max_interventions: int = 1
    # Candidate scoring is mechanical; the cheap tier is enough.
    relevance_model: str = "claude-haiku-4-5"

    brave_api_key: str = ""
    exa_api_key: str = ""

    logfire_token: str = ""

    odds_api_key: str = ""
    api_football_key: str = ""
    # Canned fixtures are display-only: a demo pass never records results or
    # publishes snapshots, so fake scores cannot leak into the forecast inputs.
    fixtures_demo: bool = False
    # Serve Polymarket from the canned fixture so a live run needs no network for data.
    polymarket_demo: bool = False

    data_dir: Path = REPO_ROOT / "data"
    focus_team: str = "england"
    n_sims: int = 10_000

    # Recent-form weighting, off: the backtest scored every setting worse than single-decay (knob at 0 is a no-op).
    form_half_life_days: float = 0.0
    form_weight: float = 0.0
    # The live impact path differences two reach sims, so its Monte-Carlo error
    # is wider than a single run's; held high enough that a one-goal swing clears
    # the noise floor rather than reading as a spurious negative move.
    impact_n_sims: int = 50_000

    aws_region: str = "eu-west-2"
    dynamo_endpoint: str = ""
    dynamo_table: str = "wolves-forecaster"
    bucket: str = BUCKET_DEV
    storage_mode: StorageMode = "both"

    runs_root: Path = REPO_ROOT / "runs"
    # Also the live-overlay impact rebuild cadence, so the in-match forecast tracks the clock.
    live_poll_interval_s: float = 30.0
    # Several missed fast polls plus jitter before consumers treat the state as stale.
    live_stale_after_s: int = 150
    # Away from a live window the loop slows down, and with --until-idle it
    # exits once no kickoff falls inside the grace horizon.
    live_idle_interval_s: float = 900.0
    # The idle wait probes for a freshly published agent forecast at this cadence
    # so the impact lip re-anchors within one probe rather than one idle gap.
    impact_anchor_probe_interval_s: float = 60.0
    # One missed idle poll plus slack: between games "stale" must mean stuck, not resting.
    live_idle_stale_after_s: int = 1080
    live_idle_grace_hours: float = 6.0

    # Live shot/possession blend into the in-match goal rates. The confidence weight
    # is minute / (minute + halflife), so signals earn trust as the match unfolds; the
    # cap bounds how far one side's rate can move so a freak early shot count cannot run away.
    live_blend_shots: bool = True
    live_blend_halflife_minutes: float = 90.0
    live_blend_conversion_prior: float = 0.30
    live_blend_multiplier_cap: float = 2.0
    live_blend_possession_tilt: float = 0.10

    # Calendar-aware agent spend (wolves/run_policy.py): the day's phase sets the ceiling, weighted to the knockouts.
    agent_ceiling_opening_usd: float = 4.00
    agent_ceiling_big_group_usd: float = 5.00
    agent_ceiling_group_usd: float = 4.00
    agent_ceiling_rest_usd: float = 3.50
    agent_ceiling_r32_r16_usd: float = 5.50
    agent_ceiling_qf_final_usd: float = 5.50
    # Hidden hard-stop cushion above the day's ceiling; the agent plans against the ceiling and never sees this.
    agent_ceiling_headroom_usd: float = 2.00
    agent_big_team_count: int = 8
    tool_timeout_seconds: float = 30.0
    tool_result_max_chars: int = 8000
    article_cache_max_age_hours: float = 48.0
    # Published numbers are re-simulated at this fidelity regardless of --sims.
    publish_n_sims: int = 50_000
    # Parameter draws behind the fixtures-page W/D/L curves; analytic, so cheap to raise.
    wdl_curve_draws: int = 500

    bookmaker_leg_weight: float = 1.0
    polymarket_leg_weight: float = 1.0

    agent_submit_retries: int = 3
    agent_structural_repair_attempts: int = 2

    graph_max_waves: int = 8
    # In-call output validation retries for the master's structured patch; a
    # live run ended planning after a truncated reply burned the old budget of 2.
    graph_master_output_retries: int = 4
    graph_max_nodes: int = 16
    graph_max_wave_workers: int = 5
    graph_max_research_nodes: int = 6
    graph_max_quant_nodes: int = 6
    graph_max_forecast_nodes: int = 3
    graph_max_critic_nodes: int = 3
    graph_research_timeout_s: int = 300
    graph_quant_timeout_s: int = 600
    graph_forecast_timeout_s: int = 900
    # One extra window for a forecast node that times out mid-steelman,
    # demonstrably one round from acceptance.
    graph_forecast_grace_s: int = 180
    graph_critic_timeout_s: int = 180
    graph_research_request_limit: int = 32
    graph_quant_request_limit: int = 28
    graph_forecast_request_limit: int = 24
    # A pre-mortem critic reads evidence, mixtures and the branch audit; 8 starved it.
    graph_critic_request_limit: int = 16
    graph_research_tool_budget: int = 12
    # Slots held back from searching so a research node can always fetch what it cites.
    graph_research_fetch_floor: int = 3
    graph_quant_tool_budget: int = 24
    graph_forecast_tool_budget: int = 16
    graph_critic_tool_budget: int = 6
    graph_quant_python_call_limit: int = 8

    market_movement_noise_floor_pp: float = 0.7

    escalation_threshold_pp: float = 2.0
    escalation_reference_p: float = 0.10
    governor_window: int = 20
    governor_shrink_weight: float = 0.5
    dispersion_governor_min_n: int = 20
    distribution_quantiles: list[float] = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]
    distribution_bins: int = 20
    story_team_count: int = 8
    dispersion_floor_enabled: bool = True
    weight_dilution_min_combined: float = 0.25
    extremising_d: float = 1.0
    # The prior extremising pushes away from.
    extremising_anchor: Literal["baseline", "market", "blend"] = "baseline"
    longshot_shade_alpha: float = 0.0
    scenario_lifecycle_enforcement: str = "soft"
    agent_evening_debrief: bool = False

    # Explicit per-run override (run-now and workflow dispatch set it);
    # unset means the calendar policy decides (wolves/run_policy.py).
    agent_run_ceiling_usd: float | None = None
    agent_run_ceiling_max_usd: float = 9.00
    agent_live_failed_attempt_limit: int = 5
    agent_live_active_ttl_minutes: int = 180
    graph_forecast_reserve_usd: float = 1.30
    graph_forecast_reserve_llm_calls: int = 26
    graph_referee_reserve_usd: float = 0.45
    graph_referee_reserve_llm_calls: int = 4
    # A useful follow-up is a quant adjudication whose first call runs ~$0.5; below this headroom the gate releases.
    graph_followup_floor_usd: float = 0.55

    # Zero recovers the exact single-pass behaviour.
    graph_max_revisions: int = 1
    graph_revision_reserve_usd: float = 1.10
    graph_premortem_enabled: bool = True
    graph_premortem_on_escalation_only: bool = True
    # Each analytical tail gates the forecast until priced, so cap how many one premortem can open.
    graph_max_critic_tails: int = 3
    graph_debrief_enabled: bool = True

    @property
    def lessons_path(self) -> Path:
        return self.runs_root / LESSONS.key()

    @property
    def calibration_path(self) -> Path:
        return self.runs_root / CALIBRATION.key()

    @property
    def stream_path(self) -> Path:
        return self.runs_root / "agent-state" / "stream.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
