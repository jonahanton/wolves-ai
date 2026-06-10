"""Agent runner: --dev is offline and $0; --live meters real APIs behind --confirm-spend."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta

from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from wolves import ENGINE_VERSION
from wolves.agent.attribution import decompose
from wolves.agent.calibration import CalibrationLedger
from wolves.agent.consensus import publish_scale
from wolves.agent.deps import AgentDeps
from wolves.agent.fakes import ScriptedLLM
from wolves.agent.forecast_artifact import govern_outputs, mixed_outputs, worlds_from_payload
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.memory import RunMemory
from wolves.agent.scenarios import ScenarioRegistry
from wolves.agent.scoring import score_yesterday
from wolves.agent.source_memory import SourceMemory
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import ApiFootballClient, FakeFixturesClient, FixturesClient
from wolves.clients.odds import (
    FakeOddsClient,
    FakePolymarketClient,
    GammaPolymarketClient,
    OddsClient,
    PolymarketClient,
    TheOddsApiClient,
)
from wolves.config import Settings
from wolves.connectors import FakeFetchClient, FakeSearchClient, ObservedWeb, build_web
from wolves.forecast import Forecaster
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.contracts import ForecastOutput, GraphPatch, LedgerEvidence, NodePatch, QuantOutput, ResearchOutput
from wolves.graph.fakes import scripted_model
from wolves.graph.observed_model import ObservedModel
from wolves.graph.runner import GraphModels, GraphRunResult, run_graph
from wolves.llm.anthropic import build_llm
from wolves.llm.client import LLMClient
from wolves.llm.observed import ObservedLLM
from wolves.observability import (
    Caps,
    InMemoryTracer,
    ObservedRuntime,
    build_logfire_tracer,
    build_runtime,
    configure_cli_logging,
)
from wolves.quant.observed import ObservedQuant
from wolves.s3.agent_state import build_agent_state_store
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.client import S3UnavailableError
from wolves.s3.layout import SCENARIOS, SOURCES_SEEN, run_dir
from wolves.s3.publish import SnapshotPublisher
from wolves.snapshot import (
    AgentBlock,
    AttributionOut,
    CalibrationSummary,
    GovernorOut,
    LedgerEntryOut,
    NarrativeBlock,
    RunMeta,
    ScenarioWeightOut,
    Snapshot,
    WorldOut,
)
from wolves.tools._budget_gate import BudgetGate

logger = logging.getLogger(__name__)


def _dev_submission(as_of: str) -> dict:
    return {
        "artifact_id": "mixture-001",
        "narrative": {
            "england_story": (
                "England's camp is calm: the keeper trained in full and the market still makes them "
                "third favourites behind Spain and France."
            ),
            "slot_rationales": {str(m): f"Slot {m}: the rating gap favours the group winner." for m in range(73, 89)},
            "travel_memo": "Win Group L and England stay on the east coast; finishing second buys a longer trip.",
        },
        "scenario_weights": [],
        "evidence_ids": ["led-0001"],
    }


def _dev_models(runtime: ObservedRuntime, as_of: str) -> GraphModels:
    """A canned full graph walk: research and quant waves, then a forecast
    node that cites the quant artifact and submits through the validator."""
    expiry = (datetime.fromisoformat(as_of) + timedelta(days=3)).date().isoformat()

    research = scripted_model(
        [
            [("web_search", {"query": "England keeper fitness", "freshness": "pd"})],
            ResearchOutput(
                summary="Keeper trained in full; FA statement confirms availability.",
                evidence=[
                    LedgerEvidence(
                        claim="First-choice keeper confirmed fit by the FA",
                        source_url="https://www.reuters.com/world/example-article-2026",
                        quote="trained in full",
                        status="confirmed",
                        mechanism="keeper returns to the XI",
                        proposed_delta=15.0,
                        expiry=expiry,
                        team_id="england",
                    )
                ],
            ),
        ],
        model_name="dev-research",
    )

    quant = scripted_model(
        [
            QuantOutput(
                summary="Baseline digest computed: England title 7.2pp at 50k sims, market gap -4.0pp.",
                findings=["England 7.2pp title; market 11.2pp; the gap inverts to +0.099 strength."],
                headline_value=0.072,
            )
        ],
        model_name="dev-quant",
    )

    forecast = scripted_model(
        [
            [("ledger_query", {"team_id": "england"})],
            [
                (
                    "scenario_update",
                    {
                        "action": "open",
                        "name": f"keeper_watch_{as_of}",
                        "weight": 0.2,
                        "reason": "monitor fitness into the next matchday",
                    },
                ),
                ("write_journal", {"text": "Keeper confirmed fit; sim and market agree England are third favourites."}),
                ("submit_forecast", _dev_submission(as_of)),
            ],
            ForecastOutput(summary="Submitted the baseline-anchored forecast."),
        ],
        model_name="dev-forecast",
    )

    def forecast_wave(prompt: str) -> GraphPatch:
        artifact_ids = sorted(set(re.findall(r"(?:evidence|quant)-\d{3}", prompt)))
        return GraphPatch(
            ops=[
                NodePatch(
                    node_id="forecast",
                    kind="forecast",
                    objective="Submit today's forecast",
                    brief="Weigh the keeper evidence, run the sim and submit.",
                    input_artifact_ids=artifact_ids,
                )
            ],
            reason="Dossier ready; move to the forecast.",
        )

    master = scripted_model(
        [
            GraphPatch(
                ops=[
                    NodePatch(
                        node_id="research-keeper",
                        kind="research",
                        objective="England keeper fitness",
                        brief="Confirm from primary sources whether the first-choice keeper is fit to start.",
                    ),
                    NodePatch(
                        node_id="quant-baseline",
                        kind="quant",
                        objective="Baseline digest",
                        brief="Compute the baseline title table and the England market gap.",
                    ),
                ],
                reason="Check the keeper story and the baseline before forecasting.",
            ),
            forecast_wave,
            GraphPatch(stop=True, reason="Submission accepted."),
        ],
        model_name="dev-master",
    )

    idle = scripted_model([], model_name="dev-idle")

    def observed(model: Model) -> ObservedModel:
        return ObservedModel(model, runtime=runtime)

    return GraphModels(
        master=observed(master),
        nodes={
            "research": observed(research),
            "quant": observed(quant),
            "forecast": observed(forecast),
            "critic": observed(idle),
        },
    )


def _build_deps(
    *,
    settings: Settings,
    runtime: ObservedRuntime,
    llm: LLMClient,
    web: ObservedWeb,
    odds: OddsClient,
    polymarket: PolymarketClient,
    fixtures: FixturesClient,
    run_id: str,
    as_of: str,
) -> AgentDeps:
    forecaster: Forecaster | None = None
    try:
        forecaster = Forecaster(settings)
        forecaster.fit(as_of=date.fromisoformat(as_of))
    except Exception as exc:
        forecaster = None
        logger.warning("run continues without a fitted forecaster: %s", exc)
    return AgentDeps(
        runtime=runtime,
        llm=ObservedLLM(llm, runtime),
        web=web,
        odds=odds,
        polymarket=polymarket,
        fixtures=fixtures,
        ledger=EvidenceLedger(run_dir(settings.runs_root, run_id) / "ledger.jsonl"),
        memory=RunMemory(runs_root=settings.runs_root, run_id=run_id, lessons_path=settings.lessons_path),
        source_memory=SourceMemory(settings.runs_root / SOURCES_SEEN.key()),
        scenarios=ScenarioRegistry(settings.runs_root / SCENARIOS.key()),
        quant=ObservedQuant(runtime),
        gate=BudgetGate(),
        settings=settings,
        as_of=as_of,
        forecaster=forecaster,
        limits=ValidatorLimits(
            escalation_threshold_pp=settings.escalation_threshold_pp,
            escalation_reference_p=settings.escalation_reference_p,
        ),
    )


def _calibration_block(settings: Settings) -> CalibrationSummary | None:
    ledger = CalibrationLedger(settings.calibration_path)
    scores = ledger.scores()
    if not scores:
        return None
    recent = scores[-settings.governor_window :]

    def means(metric: str) -> dict[str, float]:
        out: dict[str, list[float]] = {}
        for score in recent:
            for name, value in getattr(score, metric).items():
                out.setdefault(name, []).append(value)
        return {name: round(sum(v) / len(v), 4) for name, v in out.items()}

    pnls = [s.adjustment_pnl for s in recent if s.adjustment_pnl is not None]
    return CalibrationSummary(
        matches_scored=len(recent),
        brier=means("brier"),
        log_loss=means("log_loss"),
        adjustment_pnl=round(sum(pnls), 4) if pnls else None,
        governor_scale=ledger.scale(window=settings.governor_window),
    )


def _build_snapshot(
    *,
    settings: Settings,
    deps: AgentDeps,
    result: GraphRunResult,
    run_id: str,
    n_sims: int,
    seed: int,
) -> Snapshot | None:
    submission = result.submission
    assert submission is not None
    if deps.forecaster is None or deps.artifacts is None:
        logger.error("run %s: no fitted forecaster, the artifact cannot publish; no snapshot", run_id)
        return None
    artifact = deps.artifacts.get(submission.artifact_id)
    assert artifact is not None
    worlds = worlds_from_payload(artifact.payload)
    outputs = mixed_outputs(deps.forecaster, worlds, n_sims=n_sims, seed=seed)

    governor_scale = CalibrationLedger(settings.calibration_path).scale(window=settings.governor_window)
    effective_d = publish_scale(
        extremising_d=settings.extremising_d,
        governor_scale=governor_scale,
        shrink_weight=settings.governor_shrink_weight,
    )
    governor = None
    if effective_d != 1.0:
        anchor = deps.forecaster.sim_outputs(n_sims=n_sims, seed=seed)
        govern_outputs(outputs, anchor, d=effective_d)
        governor = GovernorOut(scale=governor_scale, effective_d=effective_d)
        logger.warning("run %s: governor active, publishing at d=%.2f", run_id, effective_d)

    attribution = _attribution_block(deps, outputs)
    agent_block = AgentBlock(
        narrative=NarrativeBlock(**submission.narrative.model_dump()),
        artifact_id=submission.artifact_id,
        ledger_entries=[
            LedgerEntryOut(**{**e.model_dump(mode="json"), "created_at": e.created_at.isoformat()})
            for e in deps.ledger.all()
        ],
        scenario_weights=[ScenarioWeightOut(**w.model_dump()) for w in submission.scenario_weights],
        worlds=[
            WorldOut(
                name=w.name,
                weight=w.weight,
                perturbations=[pert.model_dump(mode="json") for pert in w.perturbations],
            )
            for w in worlds
        ],
        escalations=result.escalations or [],
        market_justification=submission.market_justification,
        change_justification=submission.change_justification,
        inconsistency_note=submission.inconsistency_note,
        attribution=attribution,
        governor=governor,
        calibration=_calibration_block(settings),
    )
    return Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="agent",
        ),
        england=outputs.england,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
        agent=agent_block,
    )


def _attribution_block(deps: AgentDeps, outputs) -> AttributionOut | None:
    from wolves.insights.what_changed import load_latest_snapshot

    if deps.forecaster is None or not deps.as_of:
        return None
    try:
        previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of))
        if previous is None:
            return None
        previous_as_of = datetime.fromisoformat(previous.run.created_at).date()
        submitted = {t.team_id: t.champion_prob for t in outputs.teams}
        report = decompose(
            deps.forecaster,
            as_of=date.fromisoformat(deps.as_of),
            previous_as_of=previous_as_of,
            submitted=submitted,
        )
        return AttributionOut(bracket_pp=report.bracket_pp, refit_pp=report.refit_pp, residual_pp=report.residual_pp)
    except Exception as exc:
        logger.warning("attribution skipped: %s", exc)
        return None


async def _run(args: argparse.Namespace, settings: Settings) -> int:
    as_of = args.as_of or datetime.now(UTC).date().isoformat()
    run_id = datetime.now(UTC).strftime("agent-%Y%m%d-%H%M%S")
    started = time.monotonic()
    publisher = SnapshotPublisher(settings)
    if not publisher.run_enabled():
        logger.warning("run %s skipped: runs disabled by kill switch", run_id)
        return 0
    state = build_agent_state_store(settings)
    if state is not None:
        # An amnesia run that later pushes would overwrite good S3 state with
        # truncated state, so a failed pull ends the run cleanly instead.
        try:
            state.pull()
        except S3UnavailableError:
            logger.exception("run %s aborted: agent state pull failed", run_id)
            publisher.record_failure(
                run_id=run_id, created_at=datetime.now(UTC).isoformat(timespec="seconds"), started=started
            )
            return 1
    score_yesterday(settings, as_of=as_of, run_id=run_id)

    if args.live:
        ceiling = args.ceiling if args.ceiling is not None else settings.agent_run_ceiling_usd
        caps = Caps(max_cost_micros=int(ceiling * 1_000_000))
        tracer = build_logfire_tracer(settings) if settings.logfire_token else InMemoryTracer()
        runtime = build_runtime(run_id=run_id, tracer=tracer, caps=caps, runs_root=settings.runs_root)
        llm: LLMClient = build_llm(settings, model=settings.worker_model)
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        # Wave planning needs the stronger model; workers stay on the cheap one.
        worker = ObservedModel(AnthropicModel(settings.worker_model, provider=provider), runtime=runtime)
        master = ObservedModel(AnthropicModel(settings.fast_model, provider=provider), runtime=runtime)
        models = GraphModels(
            master=master,
            nodes={"research": worker, "quant": worker, "forecast": worker, "critic": worker},
        )
        web = build_web(settings, runtime)
        odds: OddsClient = TheOddsApiClient(settings.odds_api_key) if settings.odds_api_key else FakeOddsClient()
        polymarket: PolymarketClient = GammaPolymarketClient()
        fixtures: FixturesClient = (
            ApiFootballClient(settings.api_football_key) if settings.api_football_key else FakeFixturesClient()
        )
        logger.info("LIVE run %s: model=%s, ceiling=$%.2f", run_id, settings.worker_model, ceiling)
    else:
        runtime = build_runtime(run_id=run_id, tracer=InMemoryTracer(), caps=Caps(), runs_root=settings.runs_root)
        models = _dev_models(runtime, as_of)
        sample = {
            "rating_overrides": [
                {"team_id": "england", "delta_elo": 15.0, "cause": "keeper fit", "ledger_ids": ["led-0001"]}
            ]
        }
        llm = ScriptedLLM(turns=[], structured=[sample, sample])
        web = ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient())
        odds = FakeOddsClient()
        polymarket = FakePolymarketClient()
        fixtures = FakeFixturesClient()
        logger.info("dev run %s: scripted models and fixture clients, $0 spend", run_id)

    deps = _build_deps(
        settings=settings,
        runtime=runtime,
        llm=llm,
        web=web,
        odds=odds,
        polymarket=polymarket,
        fixtures=fixtures,
        run_id=run_id,
        as_of=as_of,
    )
    if not args.live:
        # The scripted forecast submits by reference, so the dev run seeds the
        # computed artifact a real quant node would have registered.
        store = RunArtifactStore(ArtifactStore(settings), run_id=run_id)
        store.add(
            kind="mixture",
            created_by="dev-seed",
            summary="dev keeper mixture",
            payload={
                "weights": {"keeper_fit": 0.8, "keeper_doubt": 0.2},
                "worlds": {
                    "keeper_fit": {"perturbations": []},
                    "keeper_doubt": {"perturbations": [{"team": "england", "delta": -0.03, "reason": "keeper doubt"}]},
                },
                "mixture": {},
            },
        )
        deps.artifacts = store
    try:
        result = await run_graph(deps, as_of=as_of, models=models)
    except Exception:
        publisher.record_failure(
            run_id=run_id, created_at=datetime.now(UTC).isoformat(timespec="seconds"), started=started
        )
        raise
    finally:
        await web.aclose()
        await odds.aclose()
        await polymarket.aclose()
        await fixtures.aclose()
        await llm.aclose()

    spent = runtime.budget.cost_micros / 1e6
    if result.submission is None:
        runtime.shutdown()
        logger.error(
            "run %s produced no valid submission (budget_exhausted=%s, failures=%d); no snapshot written",
            run_id,
            result.budget_exhausted,
            result.validation_failures,
        )
        if state is not None:
            state.push(run_id=run_id)
        publisher.record_failure(
            run_id=run_id, created_at=datetime.now(UTC).isoformat(timespec="seconds"), started=started
        )
        return 1

    snapshot = _build_snapshot(
        settings=settings,
        deps=deps,
        result=result,
        run_id=run_id,
        n_sims=args.sims,
        seed=args.seed,
    )
    runtime.shutdown()
    if snapshot is not None:
        publisher.publish(snapshot, as_of=date.fromisoformat(as_of), started=started)
    if state is not None:
        state.push(run_id=run_id)
    logger.info(
        "run %s complete in %d wave(s): artifact %s, %d escalation(s), cost $%.4f",
        run_id,
        result.waves,
        result.submission.artifact_id,
        len(result.escalations or []),
        spent,
    )
    return 0


def main() -> None:
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the forecast agent")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dev", action="store_true", help="offline run: scripted models and fixtures, $0 spend")
    mode.add_argument("--live", action="store_true", help="metered run against real APIs")
    parser.add_argument("--confirm-spend", action="store_true", help="required with --live")
    parser.add_argument("--ceiling", type=float, default=None, help="per-run dollar ceiling for --live")
    parser.add_argument("--sims", type=int, default=settings.n_sims)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--as-of", type=str, default=None)
    add_storage_argument(parser)
    args = parser.parse_args()
    settings = apply_storage_choice(settings, args.storage)

    if args.live:
        if not settings.anthropic_api_key:
            parser.error("--live requires ANTHROPIC_API_KEY to be set")
        if not args.confirm_spend:
            parser.error("--live requires --confirm-spend with a per-run dollar ceiling")
        ceiling = args.ceiling if args.ceiling is not None else settings.agent_run_ceiling_usd
        if ceiling <= 0 or ceiling > settings.agent_run_ceiling_max_usd:
            parser.error(f"--ceiling must be in (0, {settings.agent_run_ceiling_max_usd:.2f}]")

    sys.exit(asyncio.run(_run(args, settings)))


if __name__ == "__main__":
    main()
