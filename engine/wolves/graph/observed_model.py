from __future__ import annotations

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

from wolves.llm.pricing import cost_micros
from wolves.observability.runtime import ObservedRuntime


class ObservedModel(WrapperModel):
    """The only path graph agents reach a model.

    Caps and the dollar ceiling are charged before delegation; the call runs
    inside a traced generation; cost lands on the budget afterwards. Usage is
    mapped explicitly to the pricing dict keys because passing RequestUsage
    straight through would silently zero the ceiling."""

    def __init__(self, wrapped: Model, *, runtime: ObservedRuntime, actor: str = "graph") -> None:
        super().__init__(wrapped)
        self._runtime = runtime
        self._actor = actor

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        self._runtime.charge_llm()
        with self._runtime.observe(
            kind="llm_call",
            actor=self._actor,
            name=f"llm:{self.model_name}",
            as_generation=True,
            model=self.model_name,
        ) as rec:
            response = await super().request(messages, model_settings, model_request_parameters)
            usage = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "cache_write": response.usage.cache_write_tokens,
                "cache_read": response.usage.cache_read_tokens,
            }
            cost = cost_micros(response.model_name or self.model_name, usage)
            self._runtime.add_cost(cost)
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
