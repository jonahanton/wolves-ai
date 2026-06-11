from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from wolves.llm.pricing import cost_micros
from wolves.observability.runtime import ObservedRuntime

# Automatic prompt caching: the server moves the breakpoint forward as an
# agent's history grows, so multi-turn nodes pay cache-read rates for their
# replayed prefix. Non-Anthropic models ignore the extra key.
CACHE_SETTINGS = AnthropicModelSettings(anthropic_cache="5m")


def _usage_dict(usage: Any) -> dict[str, int]:
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_write": usage.cache_write_tokens,
        "cache_read": usage.cache_read_tokens,
    }


class ObservedModel(WrapperModel):
    """The only path graph agents reach a model.

    Caps and the dollar ceiling are charged before delegation; the call runs
    inside a traced generation; cost lands on the budget afterwards. Usage is
    mapped explicitly to the pricing dict keys because passing RequestUsage
    straight through would silently zero the ceiling."""

    def __init__(
        self, wrapped: Model, *, runtime: ObservedRuntime, actor: str = "graph", hold_back_micros: int = 0
    ) -> None:
        super().__init__(wrapped)
        self._runtime = runtime
        self._actor = actor
        self._hold_back_micros = hold_back_micros

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        reservation = self._runtime.charge_llm(hold_back_micros=self._hold_back_micros)
        with self._runtime.observe(
            kind="llm_call",
            actor=self._actor,
            name=f"llm:{self.model_name}",
            as_generation=True,
            model=self.model_name,
        ) as rec:
            response = await super().request(messages, model_settings, model_request_parameters)
            usage = _usage_dict(response.usage)
            cost = cost_micros(response.model_name or self.model_name, usage)
            self._runtime.add_cost(cost, reservation=reservation)
            rec.set_output(
                {"parts": len(response.parts)},
                usage={**usage, "total": usage["input"] + usage["output"]},
                cost={"total": round(cost / 1e6, 6)},
                model=response.model_name or self.model_name,
            )
            rec.note(
                summary=f"{self.model_name}: {usage['input']}->{usage['output']} tok, ${cost / 1e6:.4f}",
                model=response.model_name or self.model_name,
                usage=usage,
                cost_micros=cost,
            )
            return response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        # Nothing streams today, but a future run_stream call must not bypass
        # the ceiling: charge before the call, settle cost when the stream closes.
        reservation = self._runtime.charge_llm(hold_back_micros=self._hold_back_micros)
        async with super().request_stream(messages, model_settings, model_request_parameters, run_context) as stream:
            try:
                yield stream
            finally:
                usage = _usage_dict(stream.usage())
                self._runtime.add_cost(cost_micros(self.model_name, usage), reservation=reservation)
