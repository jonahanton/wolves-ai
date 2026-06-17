from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic

from wolves.config import Settings
from wolves.llm.client import LLMClient, LLMResponse, ToolTurn, ToolUseBlock


def _usage_counts(usage: Any) -> dict[str, int]:
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    return {
        # The raw API's input_tokens excludes cache tokens; pricing follows the
        # genai-prices convention where input includes them, so fold them in here.
        "input": int(getattr(usage, "input_tokens", 0) or 0) + cache_write + cache_read,
        "output": int(getattr(usage, "output_tokens", 0) or 0),
        "cache_write": cache_write,
        "cache_read": cache_read,
    }


class AnthropicClient(LLMClient):
    """Structured output over the Anthropic Messages API.

    The response schema is passed as the only tool with a forcing `tool_choice`, so
    the model's `tool_use.input` is the validated payload."""

    provider = "anthropic"

    def __init__(
        self,
        model: str,
        *,
        api_key: str,
        client: AsyncAnthropic | None = None,
        max_retries: int = 4,
    ) -> None:
        self.model = model
        self._client = client or AsyncAnthropic(api_key=api_key, max_retries=max_retries)

    async def complete(
        self,
        *,
        user: str,
        schema: dict[str, Any],
        schema_name: str,
        system: str | None = None,
        max_tokens: int = 900,
        temperature: float | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user}],
            "tools": [
                {
                    "name": schema_name,
                    "description": "Return the requested structured output.",
                    "input_schema": schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": schema_name},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if system:
            kwargs["system"] = system

        message = await self._client.messages.create(**kwargs)

        tool_input: dict[str, Any] | None = None
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "tool_use" and getattr(block, "name", None) == schema_name:
                tool_input = block.input
            elif btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "thinking":
                thinking_parts.append(getattr(block, "thinking", ""))

        if tool_input is None:
            joined = "".join(text_parts).strip()
            try:
                tool_input = json.loads(joined)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Anthropic returned no structured output: {joined[:300]}") from exc

        return LLMResponse(
            data=tool_input,
            text=json.dumps(tool_input),
            model=self.model,
            provider=self.provider,
            usage=_usage_counts(message.usage),
            response_id=message.id,
            tool_calls=[{"name": schema_name, "input": tool_input}],
            reasoning="\n".join(p for p in thinking_parts if p) or None,
        )

    async def complete_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float | None = None,
    ) -> ToolTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "auto"},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if system:
            kwargs["system"] = system

        message = await self._client.messages.create(**kwargs)

        content: list[dict[str, Any]] = []
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_use_blocks: list[ToolUseBlock] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            # Echo every block back verbatim next turn; the API rejects a
            # conversation that drops a turn's thinking/tool_use blocks.
            content.append(block.model_dump())
            if btype == "tool_use":
                tool_use_blocks.append(
                    ToolUseBlock(
                        id=getattr(block, "id", ""),
                        name=getattr(block, "name", ""),
                        input=getattr(block, "input", {}) or {},
                    )
                )
            elif btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "thinking":
                thinking_parts.append(getattr(block, "thinking", ""))

        return ToolTurn(
            content=content,
            text="".join(text_parts).strip(),
            stop_reason=getattr(message, "stop_reason", "") or "",
            model=self.model,
            provider=self.provider,
            tool_use_blocks=tool_use_blocks,
            usage=_usage_counts(message.usage),
            response_id=message.id,
            reasoning="\n".join(p for p in thinking_parts if p) or None,
        )

    async def aclose(self) -> None:
        await self._client.close()


def build_llm(settings: Settings, *, model: str | None = None) -> AnthropicClient:
    return AnthropicClient(
        model or settings.fast_model,
        api_key=settings.anthropic_api_key,
        max_retries=settings.anthropic_max_retries,
    )
