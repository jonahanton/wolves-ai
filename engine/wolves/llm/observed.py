from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from wolves.llm.client import LLMClient, ToolTurn, harden_schema
from wolves.llm.pricing import cost_micros
from wolves.observability.runtime import ObservedRuntime

T = TypeVar("T", bound=BaseModel)


class ObservedLLM:
    """The only way agents reach an LLM. Every call is charged against caps and
    enclosed in a traced generation mirrored to local JSONL."""

    def __init__(self, client: LLMClient, runtime: ObservedRuntime) -> None:
        self._client = client
        self._runtime = runtime

    async def structured(
        self,
        *,
        prompt_name: str,
        actor: str,
        response_model: type[T],
        user: str,
        system: str | None = None,
        max_tokens: int = 900,
        temperature: float = 0.0,
    ) -> T:
        schema = harden_schema(response_model.model_json_schema())
        schema_name = response_model.__name__

        reservation = self._runtime.charge_llm()
        with self._runtime.observe(
            kind="llm_call",
            actor=actor,
            name=f"llm:{prompt_name}",
            as_generation=True,
            model=self._client.model,
            input={"system": system, "user": user},
            metadata={
                "provider": self._client.provider,
                "prompt_name": prompt_name,
                "schema": schema_name,
            },
            model_parameters={"temperature": temperature, "max_tokens": max_tokens},
        ) as rec:
            resp = await self._client.complete(
                user=user,
                schema=schema,
                schema_name=schema_name,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            cost = cost_micros(resp.model, resp.usage)
            resp.cost_micros = cost
            self._runtime.add_cost(cost, reservation=reservation)

            rec.set_output(
                resp.data,
                usage={
                    **resp.usage,
                    "total": resp.usage.get("input", 0) + resp.usage.get("output", 0),
                },
                cost={"total": round(cost / 1e6, 6)},
                model=resp.model,
            )
            rec.annotate(
                provider_response_id=resp.response_id,
                reasoning=resp.reasoning,
                tool_calls=resp.tool_calls,
            )
            tokens_in = resp.usage.get("input", 0)
            tokens_out = resp.usage.get("output", 0)
            rec.note(
                summary=f"{prompt_name}: {tokens_in}->{tokens_out} tok, ${cost / 1e6:.4f}",
                prompt_name=prompt_name,
                model=resp.model,
                provider=resp.provider,
                usage=resp.usage,
                cost_micros=cost,
                response_id=resp.response_id,
                has_reasoning=bool(resp.reasoning),
            )
            return response_model.model_validate(resp.data)

    async def tool_turn(
        self,
        *,
        actor: str,
        prompt_name: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> ToolTurn:
        """One observed, charged assistant turn of a ReAct tool loop. The caller
        owns the message list and the loop; this owns one turn + its observation."""
        reservation = self._runtime.charge_llm()
        with self._runtime.observe(
            kind="llm_call",
            actor=actor,
            name=f"llm:{prompt_name}",
            as_generation=True,
            model=self._client.model,
            input={"system": system, "messages": messages},
            metadata={"provider": self._client.provider, "prompt_name": prompt_name},
            model_parameters={"temperature": temperature, "max_tokens": max_tokens},
        ) as rec:
            turn = await self._client.complete_tools(
                messages=messages,
                tools=tools,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            cost = cost_micros(turn.model, turn.usage)
            turn.cost_micros = cost
            self._runtime.add_cost(cost, reservation=reservation)

            tool_names = [b.name for b in turn.tool_use_blocks]
            rec.set_output(
                {"stop_reason": turn.stop_reason, "tool_calls": tool_names, "text": turn.text},
                usage={
                    **turn.usage,
                    "total": turn.usage.get("input", 0) + turn.usage.get("output", 0),
                },
                cost={"total": round(cost / 1e6, 6)},
                model=turn.model,
            )
            rec.annotate(provider_response_id=turn.response_id, reasoning=turn.reasoning)
            rec.note(
                summary=f"{prompt_name}: {turn.stop_reason}, tools={tool_names}",
                prompt_name=prompt_name,
                model=turn.model,
                provider=turn.provider,
                usage=turn.usage,
                cost_micros=cost,
                response_id=turn.response_id,
                stop_reason=turn.stop_reason,
            )
            return turn
