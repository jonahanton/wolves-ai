"""Run one quant node against a real model: the cheap harness for tuning
quant behaviour without paying for a full graph run."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from wolves.agent.fakes import ScriptedLLM
from wolves.clients.api_football import FakeFixturesClient
from wolves.clients.odds import FakeOddsClient, FakePolymarketClient
from wolves.config import Settings
from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.contracts import NodePatch
from wolves.graph.nodes import execute_brief
from wolves.graph.observed_model import ObservedModel
from wolves.observability import Caps, InMemoryTracer, build_runtime, configure_cli_logging
from wolves.run_agent import _build_deps
from wolves.s3.artifacts import ArtifactStore


async def main() -> int:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Run one quant node against a real model")
    parser.add_argument("--brief", required=True, help="the decision question, phrased as a master brief")
    parser.add_argument("--objective", default="Quant analysis")
    parser.add_argument("--ceiling", type=float, default=0.80)
    parser.add_argument("--confirm-spend", action="store_true")
    args = parser.parse_args()
    if not args.confirm_spend:
        print("refusing to spend without --confirm-spend", file=sys.stderr)
        return 2

    settings = Settings()
    run_id = f"quantmock-{datetime.now(UTC):%Y%m%d-%H%M%S}"
    runtime = build_runtime(
        run_id=run_id,
        tracer=InMemoryTracer(),
        caps=Caps(
            max_cost_micros=int(args.ceiling * 1_000_000),
            max_llm_calls=60,
            max_quant_executions=settings.graph_quant_tool_budget * 3,
        ),
        runs_root=settings.runs_root,
    )
    deps = _build_deps(
        settings=settings,
        runtime=runtime,
        llm=ScriptedLLM(turns=[], structured=[]),
        web=ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient()),
        odds=FakeOddsClient(),
        polymarket=FakePolymarketClient(),
        fixtures=FakeFixturesClient(),
        run_id=run_id,
        as_of=str(datetime.now(UTC).date()),
    )
    store = RunArtifactStore(ArtifactStore(settings), run_id=run_id)
    store.add(
        kind="mixture",
        created_by="runtime",
        summary="Baseline single-world mixture: the unperturbed champion simulation, submit-ready as-is.",
        payload={"weights": {"baseline": 1.0}, "worlds": {"baseline": {"perturbations": []}}, "mixture": {}},
    )
    deps.artifacts = store

    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = ObservedModel(
        AnthropicModel(settings.graph_quant_model or settings.worker_model, provider=provider), runtime=runtime
    )
    op = NodePatch(
        node_id="quant-mock",
        kind="quant",
        objective=args.objective,
        brief=args.brief,
        input_artifact_ids=["mixture-001"],
    )
    with runtime.run_trace(title=f"quant mock {run_id}"):
        outcome = await execute_brief(op, deps=deps, store=store, model=model)
    runtime.shutdown()

    print(json.dumps(outcome.model_dump(mode="json"), indent=2))
    for artifact_id in outcome.artifact_ids:
        artifact = store.get(artifact_id)
        if artifact is not None:
            print(f"\n--- {artifact.id}: {artifact.summary}")
            print(json.dumps(artifact.payload, indent=2)[:4000])
    print(f"\ncost ${runtime.budget.cost_micros / 1e6:.4f}, llm calls {runtime.budget.llm_calls}")
    print(f"workspace: {settings.runs_root}/runs/{run_id}/workspace/quant/quant-mock")
    return 0 if outcome.ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
