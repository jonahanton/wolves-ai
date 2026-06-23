from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import anthropic
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from wolves.llm.pricing import cost_micros
from wolves.observability.runtime import ObservedRuntime

logger = logging.getLogger(__name__)

# Automatic prompt caching: the server moves the breakpoint forward as an
# agent's history grows, so multi-turn nodes pay cache-read rates for their
# replayed prefix. Non-Anthropic models ignore the extra key.
CACHE_SETTINGS = AnthropicModelSettings(anthropic_cache="5m")

_RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 529})


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, anthropic.APITimeoutError | anthropic.APIConnectionError | TimeoutError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS
    return False


@dataclass(frozen=True, kw_only=True)
class RetryPolicy:
    """Bounded backoff for a single graph LLM request."""

    max_retries: int = 2
    base_delay_s: float = 1.0
    max_delay_s: float = 20.0


DEFAULT_RETRY = RetryPolicy()


class TransientLLMError(Exception):
    """A graph LLM request still failing transiently after its retries."""

    def __init__(self, model: str, attempts: int) -> None:
        super().__init__(f"{model} failed transiently after {attempts} attempts")
        self.model = model
        self.attempts = attempts


def _usage_dict(usage: Any) -> dict[str, int]:
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_write": usage.cache_write_tokens,
        "cache_read": usage.cache_read_tokens,
    }


_PART_TEXT_CHARS = 2000


def _rendered_parts(parts: list[Any]) -> list[dict[str, str]]:
    """The response content as trace output: text and tool calls, truncated."""
    rendered: list[dict[str, str]] = []
    for part in parts:
        kind = getattr(part, "part_kind", type(part).__name__)
        tool_name = getattr(part, "tool_name", None)
        if tool_name is not None:
            rendered.append({"kind": kind, "tool": tool_name, "args": str(getattr(part, "args", ""))[:1000]})
        elif isinstance(getattr(part, "content", None), str):
            rendered.append({"kind": kind, "text": part.content[:_PART_TEXT_CHARS]})
    return rendered


class ObservedModel(WrapperModel):
    """The only path graph agents reach a model.

    Caps and the dollar ceiling are charged before delegation; the call runs
    inside a traced generation; cost lands on the budget afterwards. Usage is
    mapped explicitly to the pricing dict keys because passing RequestUsage
    straight through would silently zero the ceiling."""

    def __init__(
        self,
        wrapped: Model,
        *,
        runtime: ObservedRuntime,
        actor: str = "graph",
        operation: str | None = None,
        hold_back_micros: int = 0,
        reservation_floor_micros: int = 0,
        retry: RetryPolicy = DEFAULT_RETRY,
    ) -> None:
        super().__init__(wrapped)
        self._runtime = runtime
        self._actor = actor
        self._operation = operation
        self._hold_back_micros = hold_back_micros
        self._reservation_floor_micros = reservation_floor_micros
        self._retry = retry

    @property
    def retry(self) -> RetryPolicy:
        return self._retry

    @property
    def reservation_floor_micros(self) -> int:
        return self._reservation_floor_micros

    def for_actor(self, actor: str, *, operation: str | None = None) -> ObservedModel:
        """Attribute a model view to one graph actor."""
        return ObservedModel(
            self.wrapped,
            runtime=self._runtime,
            actor=actor,
            operation=operation,
            hold_back_micros=self._hold_back_micros,
            reservation_floor_micros=self._reservation_floor_micros,
            retry=self._retry,
        )

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        for attempt in range(self._retry.max_retries + 1):
            try:
                return await self._request_once(messages, model_settings, model_request_parameters)
            except asyncio.CancelledError:
                # A cancel means a deadline or shutdown owns the task; never fight it.
                raise
            except BaseException as exc:
                if not _is_transient(exc):
                    raise
                if attempt == self._retry.max_retries:
                    raise TransientLLMError(self.model_name, attempt + 1) from exc
                delay = min(
                    self._retry.base_delay_s * 2**attempt + random.uniform(0, 1),
                    self._retry.max_delay_s,
                )
                logger.warning(
                    "%s transient LLM error, retry %d/%d in %.1fs: %s",
                    self.model_name,
                    attempt + 1,
                    self._retry.max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    async def _request_once(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        reservation = self._runtime.charge_llm(
            hold_back_micros=self._hold_back_micros,
            reservation_floor_micros=self._reservation_floor_micros,
        )
        settled = False
        operation_metadata = (
            {
                "operation": self._operation,
                "output_tools": [tool.name for tool in model_request_parameters.output_tools],
            }
            if self._operation is not None
            else None
        )
        try:
            with self._runtime.observe(
                kind="llm_call",
                actor=self._actor,
                name=f"llm:{self._operation or self.model_name}",
                as_generation=True,
                model=self.model_name,
                input=(
                    {"messages": ModelMessagesTypeAdapter.dump_python(messages, mode="json")}
                    if self._operation is not None
                    else None
                ),
                metadata=operation_metadata,
                model_parameters=dict(model_settings or {}) if self._operation is not None else None,
            ) as rec:
                response = await super().request(messages, model_settings, model_request_parameters)
                usage = _usage_dict(response.usage)
                cost = cost_micros(response.model_name or self.model_name, usage)
                self._runtime.add_cost(cost, reservation=reservation)
                settled = True
                rec.set_output(
                    {"parts": len(response.parts), "content": _rendered_parts(response.parts)},
                    usage={**usage, "total": usage["input"] + usage["output"]},
                    cost={"total": round(cost / 1e6, 6)},
                    model=response.model_name or self.model_name,
                )
                rec.note(
                    summary=f"{self.model_name}: {usage['input']}->{usage['output']} tok, ${cost / 1e6:.4f}",
                    model=response.model_name or self.model_name,
                    usage=usage,
                    cost_micros=cost,
                    **(
                        {"operation": self._operation, "response_id": response.provider_response_id}
                        if self._operation is not None
                        else {}
                    ),
                )
                return response
        finally:
            # A failed or cancelled call never settles; without the release
            # its reservation would hold the ceiling for the rest of the run.
            if not settled:
                self._runtime.release_reservation(reservation)

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
        reservation = self._runtime.charge_llm(
            hold_back_micros=self._hold_back_micros,
            reservation_floor_micros=self._reservation_floor_micros,
        )
        settled = False
        try:
            async with super().request_stream(
                messages, model_settings, model_request_parameters, run_context
            ) as stream:
                try:
                    yield stream
                finally:
                    usage = _usage_dict(stream.usage())
                    self._runtime.add_cost(cost_micros(self.model_name, usage), reservation=reservation)
                    settled = True
        finally:
            if not settled:
                self._runtime.release_reservation(reservation)
