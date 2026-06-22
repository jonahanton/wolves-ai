from __future__ import annotations

import json
import os

import pytest
from anthropic import AsyncAnthropic
from pydantic_ai.providers.anthropic import AnthropicProvider

from wolves.agent.tools.retrieval.rank_relevance import _RANK_SETTINGS, _RANKER, _Rankings
from wolves.agent.tools.submission.referee import _REFEREE, _REFEREE_SETTINGS, RefereeReport
from wolves.config import Settings
from wolves.graph.anthropic import build_anthropic_model


@pytest.mark.smoke
async def test_live_anthropic_accepts_auxiliary_output_schemas():
    if os.environ.get("RUN_LLM_SMOKE") != "1":
        pytest.skip("RUN_LLM_SMOKE is not enabled")
    settings = Settings()
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY is not set")

    client = AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_request_timeout_s,
        max_retries=settings.anthropic_max_retries,
    )
    provider = AnthropicProvider(anthropic_client=client)
    try:
        ranking = await _RANKER.run(
            "Sub-question: Which source is relevant?\n\n"
            "Candidates:\nurl: https://www.fifa.com/\ntitle: Official FIFA news\ntier: 1",
            model=build_anthropic_model(settings.relevance_model, provider),
            model_settings=_RANK_SETTINGS,
        )
        referee = await _REFEREE.run(
            json.dumps(
                {
                    "as_of": "2026-06-22",
                    "public_surface": {"headline": "No material change.", "visible_distribution": {}},
                    "submission": {"headline": "No material change."},
                    "deterministic_validator": {"ok": True, "issues": []},
                }
            ),
            model=build_anthropic_model(
                settings.graph_referee_model or settings.graph_master_model or settings.smart_model,
                provider,
            ),
            model_settings=_REFEREE_SETTINGS,
        )
    finally:
        await client.close()

    assert isinstance(ranking.output, _Rankings)
    assert ranking.usage.requests == 1
    assert isinstance(referee.output, RefereeReport)
    assert referee.usage.requests == 1
