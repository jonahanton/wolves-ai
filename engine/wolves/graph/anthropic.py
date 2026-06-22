"""Contain Anthropic model-profile compatibility at the provider boundary."""

from __future__ import annotations

from dataclasses import replace

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider


def build_anthropic_model(model_name: str, provider: AnthropicProvider) -> AnthropicModel:
    """Build an Anthropic model with its current capability profile."""
    profile = provider.model_profile(model_name)
    if profile is None:
        raise ValueError(f"Anthropic has no capability profile for {model_name}")
    if model_name.startswith("claude-opus-4-8"):
        profile = replace(profile, supports_json_schema_output=True)
    return AnthropicModel(model_name, provider=provider, profile=profile)
