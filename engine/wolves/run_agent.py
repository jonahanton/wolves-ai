"""Agent runner: --dev is offline and $0; --live meters real APIs behind --confirm-spend."""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from wolves import ENGINE_VERSION
from wolves.agent.article_cache import ArticleCache
from wolves.agent.attribution import decompose
from wolves.agent.calibration import CalibrationLedger, total_spread_pnl
from wolves.agent.consensus import publish_scale
from wolves.agent.deps import AgentDeps, SubmissionState
from wolves.agent.fakes import ScriptedLLM
from wolves.agent.forecast_artifact import govern_outputs, mixed_outputs, simulate_worlds, worlds_from_payload
from wolves.agent.ledger import EvidenceLedger
from wolves.agent.market_base import seed_baseline_payload
from wolves.agent.memory import RunMemory
from wolves.agent.relevance_feedback import append_feedback, relevance_feedback
from wolves.agent.relevance_memory import RelevanceMemory
from wolves.agent.scenarios import ScenarioRegistry
from wolves.agent.scoring import score_yesterday
from wolves.agent.source_memory import SourceMemory
from wolves.agent.stream import band_coverage, load_stream, movement_stats, record_stream
from wolves.agent.validator import ValidatorLimits
from wolves.clients.api_football import FakeFixturesClient, FixturesClient, MergedFixturesClient
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
from wolves.live import build_fixtures_client
from wolves.llm.anthropic import build_llm
from wolves.llm.client import LLMClient
from wolves.llm.observed import ObservedLLM
from wolves.markets.blend import blend_probabilities
from wolves.markets.outright import outright_consensus
from wolves.observability import (
    Caps,
    InMemoryTracer,
    ObservedRuntime,
    build_logfire_tracer,
    build_runtime,
    configure_cli_logging,
)
from wolves.publish_distributions import build_run_distributions
from wolves.quant.observed import ObservedQuant
from wolves.run_policy import agent_ceiling
from wolves.s3.agent_state import build_agent_state_store
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.cli import add_storage_argument, apply_storage_choice
from wolves.s3.client import S3UnavailableError
from wolves.s3.fitted import FittedStateStore
from wolves.s3.layout import ARTICLE, RELEVANCE_FEEDBACK, RELEVANCE_MEMORY, SCENARIOS, SOURCES_SEEN, run_dir
from wolves.s3.publish import SnapshotPublisher
from wolves.sim.format import load_format
from wolves.sim.mc import SimResult
from wolves.sim.results_store import persisted_results, played_match_records, stored_fixtures
from wolves.snapshot import (
    AgentBlock,
    AttributionOut,
    CalibrationSummary,
    GovernorOut,
    LedgerEntryOut,
    MarketsBlock,
    NarrativeBlock,
    QuantFindingOut,
    RunMeta,
    ScenarioWeightOut,
    Snapshot,
    WorldOut,
    run_day,
)
from wolves.toolkit._budget_gate import BudgetGate

logger = logging.getLogger(__name__)


def _dev_submission(as_of: str, focus: str) -> dict:
    return {
        "artifact_id": "mixture-001",
        "narrative": {
            "headline": (
                f"Spain remain the team to beat, with {focus} close behind. Nothing in today's news moves the picture."
            ),
            "focus_story": (
                f"The {focus} camp is calm: the keeper trained in full and the market still makes them "
                "third favourites behind Spain and France."
            ),
            "slot_rationales": {str(m): f"Slot {m}: the rating gap favours the group winner." for m in range(73, 89)},
            "travel_memo": f"Win the group and {focus} stay on the east coast; finishing second buys a longer trip.",
        },
        "scenario_weights": [],
        "evidence_ids": ["led-0001"],
        # The keeper story resolved as confirmed fit, so the narrow band is
        # argued rather than widened; also the dev walk's answer to the
        # mixture_underdispersed nudge.
        "change_justification": (
            "The keeper is confirmed fit, so the day's one open story resolved and no extra width is owed."
        ),
    }


def _dev_models(runtime: ObservedRuntime, as_of: str, focus: str) -> GraphModels:
    """A canned full graph walk: research and quant waves, then a forecast
    node that cites the quant artifact and submits through the validator."""
    expiry = (datetime.fromisoformat(as_of) + timedelta(days=3)).date().isoformat()

    research = scripted_model(
        [
            [("web_search", {"query": f"{focus} keeper fitness", "freshness": "pd"})],
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
                        team_id=focus,
                    )
                ],
            ),
        ],
        model_name="dev-research",
    )

    quant = scripted_model(
        [
            QuantOutput(
                summary=f"Baseline digest computed: {focus} title 7.2pp at 50k sims, market gap -4.0pp.",
                findings=[f"{focus} 7.2pp title; market 11.2pp; the gap inverts to +0.099 strength."],
                headline_value=0.072,
            )
        ],
        model_name="dev-quant",
    )

    forecast = scripted_model(
        [
            [("ledger_query", {"team_id": focus})],
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
                (
                    "write_journal",
                    {"text": f"Keeper confirmed fit; sim and market agree {focus} are third favourites."},
                ),
                ("submit_forecast", _dev_submission(as_of, focus)),
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
                        objective=f"{focus} keeper fitness",
                        brief="Confirm from primary sources whether the first-choice keeper is fit to start.",
                    ),
                    NodePatch(
                        node_id="quant-baseline",
                        kind="quant",
                        objective="Baseline digest",
                        brief=f"Compute the baseline title table and the {focus} market gap.",
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
        forecaster.fit(as_of=date.fromisoformat(as_of), extra_results=played_match_records(settings))
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
        articles=ArticleCache(settings.runs_root / ARTICLE.prefix),
        relevance_memory=RelevanceMemory(settings.runs_root / RELEVANCE_MEMORY.key()),
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
    stream = load_stream(settings)
    spread = total_spread_pnl(scores, window=settings.governor_window)
    movement = movement_stats(stream)
    return CalibrationSummary(
        matches_scored=len(recent),
        brier=means("brier"),
        log_loss=means("log_loss"),
        adjustment_pnl=round(sum(pnls), 4) if pnls else None,
        governor_scale=ledger.scale(window=settings.governor_window),
        spread_pnl=round(spread, 4) if spread is not None else None,
        band_coverage=_rounded(band_coverage(stream)),
        movement_ratio=_rounded(movement.ratio) if movement is not None else None,
    )


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


async def _publish_fallback(
    settings: Settings, publisher: SnapshotPublisher, *, as_of: date, n_sims: int, seed: int, started: float
) -> None:
    """Publish a deterministic sim-only snapshot so a failed agent run never leaves the day dark."""
    from wolves.run import generate_snapshot, run_id_for

    try:
        # generate_snapshot drives its own event loop for the markets block.
        snapshot, sidecars = await asyncio.to_thread(
            generate_snapshot, settings, n_sims=n_sims, seed=seed, run_id=f"{run_id_for(as_of)}-fallback"
        )
        publisher.publish(snapshot, as_of=as_of, started=started, sidecars=sidecars)
        logger.warning("published deterministic fallback snapshot %s", snapshot.run.run_id)
    except Exception:
        logger.error("deterministic fallback publish failed", exc_info=True)


def _prefer_last_clean(result: GraphRunResult, state: SubmissionState, *, run_id: str) -> GraphRunResult:
    """A submission that validated clean and was withheld only by the
    escalation pause beats the deterministic fallback when the steelman
    round never completed."""
    if result.submission is not None or state.last_clean is None:
        return result
    logger.warning(
        "run %s: steelman round interrupted after a clean submission; publishing the last clean forecast", run_id
    )
    result.submission = state.last_clean
    result.escalations = state.last_clean_escalations or None
    return result


def _markets_block(deps: AgentDeps, outputs, market: dict[str, float]) -> MarketsBlock | None:
    if not market or deps.forecaster is None:
        return None
    model_probs = {t.team_id: t.champion_prob for t in outputs.teams}
    weight = deps.forecaster.champion.blend_weight
    return MarketsBlock(
        model_probs={k: round(v, 4) for k, v in model_probs.items()},
        market_probs={k: round(v, 4) for k, v in market.items()},
        blend_probs={k: round(v, 4) for k, v in blend_probabilities(model_probs, market, model_weight=weight).items()},
        model_weight=weight,
    )


def _top_probs(probs: dict[str, float], *, limit: int = 8) -> dict[str, float]:
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return {team: round(p, 4) for team, p in top}


def _quant_findings(deps: AgentDeps) -> list[QuantFindingOut]:
    if deps.artifacts is None:
        return []
    findings: list[QuantFindingOut] = []
    for record in deps.artifacts.all():
        if record.kind != "quant":
            continue
        artifact = deps.artifacts.get(record.id)
        if artifact is None:
            continue
        findings.append(
            QuantFindingOut(
                node_id=artifact.created_by,
                summary=str(artifact.payload.get("summary", ""))[:300],
                headline_value=artifact.payload.get("headline_value"),
                findings=[str(f)[:300] for f in (artifact.payload.get("findings") or [])[:5]],
            )
        )
    return findings


def _ledger_entries(ledger: EvidenceLedger, articles: ArticleCache) -> list[LedgerEntryOut]:
    """Publish ledger entries with article titles joined from the cache."""
    entries: list[LedgerEntryOut] = []
    for e in ledger.all():
        article = articles.get(e.source_url)
        entries.append(
            LedgerEntryOut(
                **{
                    **e.model_dump(mode="json"),
                    "created_at": e.created_at.isoformat(),
                    "title": article.title if article else None,
                }
            )
        )
    return entries


def _world_match_probs(
    forecaster, per_world_results: dict[str, SimResult], *, n_sims: int, seed: int, played: dict
) -> dict[str, dict[str, dict[str, float]]]:
    """Per-world W/D/L for unplayed group matches, the surface the spread P&L scores."""
    per_world: dict[str, dict[str, dict[str, float]]] = {}
    for name, sim_result in per_world_results.items():
        outputs = forecaster.sim_outputs(n_sims=n_sims, seed=seed, extra_results=played, result=sim_result)
        per_world[name] = {
            str(m.match): {"home": m.p_home, "draw": m.p_draw, "away": m.p_away}
            for m in outputs.matches
            if m.stage == "group" and m.p_draw is not None and m.match not in played
        }
    return per_world


def _build_snapshot(
    *,
    settings: Settings,
    deps: AgentDeps,
    result: GraphRunResult,
    run_id: str,
    n_sims: int,
    seed: int,
    market: dict[str, float],
) -> tuple[Snapshot, dict[str, BaseModel]] | None:
    submission = result.submission
    assert submission is not None
    if deps.forecaster is None or deps.artifacts is None:
        logger.error("run %s: no fitted forecaster, the artifact cannot publish; no snapshot", run_id)
        return None
    artifact = deps.artifacts.get(submission.artifact_id)
    assert artifact is not None
    worlds = worlds_from_payload(artifact.payload)
    played = persisted_results(settings)
    n_sims = max(n_sims, settings.publish_n_sims)
    per_world_results = simulate_worlds(deps.forecaster, worlds, n_sims=n_sims, seed=seed, extra_results=played)
    outputs = mixed_outputs(
        deps.forecaster, worlds, n_sims=n_sims, seed=seed, extra_results=played, per_world_results=per_world_results
    )

    governor_scale = CalibrationLedger(settings.calibration_path).scale(window=settings.governor_window)
    effective_d = publish_scale(
        extremising_d=settings.extremising_d,
        governor_scale=governor_scale,
        shrink_weight=settings.governor_shrink_weight,
    )
    governor = None
    anchor_result = None
    if effective_d != 1.0 or (settings.dispersion_floor_enabled and len(worlds) > 1):
        anchor_result = deps.forecaster.simulate(
            n_sims=n_sims, seed=seed, results=deps.forecaster.played_results(extra_results=played)
        )
    if effective_d != 1.0:
        anchor = deps.forecaster.sim_outputs(n_sims=n_sims, seed=seed, extra_results=played, result=anchor_result)
        govern_outputs(outputs, anchor, d=effective_d)
        governor = GovernorOut(scale=governor_scale, effective_d=effective_d)
        logger.warning("run %s: governor active, publishing at d=%.2f", run_id, effective_d)

    weights = {w.name: w.weight for w in worlds}
    distributions, sidecars = build_run_distributions(
        deps.forecaster.fmt,
        per_world_results,
        weights,
        settings=settings,
        played=frozenset(deps.forecaster.played_results(extra_results=played)),
        rng_seed=seed,
        anchor_result=anchor_result,
        effective_d=effective_d,
        stream_records=load_stream(settings),
    )
    match_probs = _world_match_probs(deps.forecaster, per_world_results, n_sims=n_sims, seed=seed, played=played)

    attribution = _attribution_block(deps, outputs)
    conditionals = artifact.payload.get("conditionals") or {}
    agent_block = AgentBlock(
        narrative=NarrativeBlock(**submission.narrative.model_dump()),
        artifact_id=submission.artifact_id,
        ledger_entries=_ledger_entries(deps.ledger, deps.articles),
        scenario_weights=[ScenarioWeightOut(**w.model_dump()) for w in submission.scenario_weights],
        worlds=[
            WorldOut(
                name=w.name,
                weight=w.weight,
                perturbations=[pert.model_dump(mode="json") for pert in w.perturbations],
                title_probs=_top_probs(conditionals.get(w.name) or {}),
                match_probs=match_probs.get(w.name, {}),
            )
            for w in worlds
        ],
        quant_findings=_quant_findings(deps),
        escalations=result.escalations or [],
        market_justification=submission.market_justification,
        change_justification=submission.change_justification,
        inconsistency_note=submission.inconsistency_note,
        attribution=attribution,
        governor=governor,
        calibration=_calibration_block(settings),
    )
    snapshot = Snapshot(
        run=RunMeta(
            run_id=run_id,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            as_of=deps.as_of,
            n_sims=n_sims,
            engine_version=ENGINE_VERSION,
            kind="agent",
        ),
        focus=outputs.focus,
        slots=outputs.slots,
        teams=outputs.teams,
        groups=outputs.groups,
        matches=outputs.matches,
        markets=_markets_block(deps, outputs, market),
        agent=agent_block,
        distributions=distributions,
    )
    return snapshot, sidecars


def _attribution_block(deps: AgentDeps, outputs) -> AttributionOut | None:
    from wolves.insights.what_changed import load_latest_snapshot

    if deps.forecaster is None or not deps.as_of:
        return None
    try:
        previous = load_latest_snapshot(deps.settings.runs_root / "snapshots", before=date.fromisoformat(deps.as_of))
        if previous is None:
            return None
        previous_as_of = date.fromisoformat(run_day(previous.run))
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
        ceiling = args.ceiling
        # The dollar ceiling is the budget; the call cap is only a runaway
        # backstop, sized so cheap-tier nodes cannot exhaust it first.
        caps = Caps(max_cost_micros=int(ceiling * 1_000_000), max_llm_calls=240, max_quant_executions=60)
        tracer = build_logfire_tracer(settings) if settings.logfire_token else InMemoryTracer()
        runtime = build_runtime(run_id=run_id, tracer=tracer, caps=caps, runs_root=settings.runs_root)
        llm: LLMClient = build_llm(settings, model=settings.relevance_model)
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)

        # Wave planning and numerical judgement need the stronger model;
        # extraction-shaped nodes run on the cheap one.
        def observed(model_name: str) -> ObservedModel:
            return ObservedModel(AnthropicModel(model_name, provider=provider), runtime=runtime)

        models = GraphModels(
            master=observed(settings.graph_master_model or settings.fast_model),
            nodes={
                "research": observed(settings.graph_research_model or settings.worker_model),
                "quant": observed(settings.graph_quant_model or settings.worker_model),
                "forecast": observed(settings.graph_forecast_model or settings.worker_model),
                "critic": observed(settings.graph_critic_model or settings.worker_model),
            },
        )
        web = build_web(settings, runtime)
        odds: OddsClient = TheOddsApiClient(settings.odds_api_key) if settings.odds_api_key else FakeOddsClient()
        polymarket: PolymarketClient = GammaPolymarketClient()
        fixtures: FixturesClient = build_fixtures_client(settings)
        logger.info(
            "LIVE run %s: master=%s, workers=%s, ceiling=$%.2f",
            run_id,
            settings.graph_master_model or settings.fast_model,
            settings.worker_model,
            ceiling,
        )
    else:
        runtime = build_runtime(run_id=run_id, tracer=InMemoryTracer(), caps=Caps(), runs_root=settings.runs_root)
        models = _dev_models(runtime, as_of, settings.focus_team)
        sample = {
            "rating_overrides": [
                {"team_id": settings.focus_team, "delta_elo": 15.0, "cause": "keeper fit", "ledger_ids": ["led-0001"]}
            ]
        }
        llm = ScriptedLLM(turns=[], structured=[sample, sample])
        web = ObservedWeb(runtime=runtime, brave=FakeSearchClient(), fetch=FakeFetchClient())
        odds = FakeOddsClient()
        polymarket = FakePolymarketClient()
        fixtures = FakeFixturesClient()
        logger.info("dev run %s: scripted models and fixture clients, $0 spend", run_id)

    # Results persisted by live passes back the fixtures tool too, so the agent
    # sees the same played matches the simulation does.
    fixtures = MergedFixturesClient(fixtures, stored=stored_fixtures(settings))
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
    store = RunArtifactStore(ArtifactStore(settings), run_id=run_id)
    if args.live:
        # Submission is by artifact reference, so a citable mixture must exist
        # even when every quant node fails; it carries both bases so even the
        # fallback never publishes one view unexamined.
        payload, summary = seed_baseline_payload(deps.forecaster, settings.runs_root / "odds-archive")
        store.add(kind="mixture", created_by="runtime", summary=summary, payload=payload)
    else:
        # The scripted forecast submits by reference, so the dev run seeds the
        # computed artifact a real quant node would have registered.
        store.add(
            kind="mixture",
            created_by="dev-seed",
            summary="dev keeper mixture",
            payload={
                "weights": {"keeper_fit": 0.8, "keeper_doubt": 0.2},
                "worlds": {
                    "keeper_fit": {"perturbations": []},
                    "keeper_doubt": {
                        "perturbations": [{"team": settings.focus_team, "delta": -0.03, "reason": "keeper doubt"}]
                    },
                },
                "mixture": {},
            },
        )
    deps.artifacts = store
    market: dict[str, float] = {}
    try:
        result = _prefer_last_clean(await run_graph(deps, as_of=as_of, models=models), deps.submission, run_id=run_id)
        if result.submission is not None and deps.forecaster is not None:
            # Fetched before the clients close: feeds the transparency MarketsBlock.
            try:
                market = await outright_consensus(settings, deps.forecaster.fmt, odds=odds, polymarket=polymarket)
            except Exception:
                logger.warning("markets fetch failed; snapshot publishes without the markets block", exc_info=True)
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
    if deps.artifacts is not None:
        # Failed runs still paid for their retrieval; their feedback counts too.
        append_feedback(
            settings.runs_root / RELEVANCE_FEEDBACK.key(),
            relevance_feedback(deps.artifacts, deps.ledger, run_id=run_id),
        )
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
        await _publish_fallback(
            settings, publisher, as_of=date.fromisoformat(as_of), n_sims=args.sims, seed=args.seed, started=started
        )
        return 1
    built = _build_snapshot(
        settings=settings,
        deps=deps,
        result=result,
        run_id=run_id,
        n_sims=args.sims,
        seed=args.seed,
        market=market,
    )
    runtime.shutdown()
    if built is not None:
        snapshot, sidecars = built
        record_stream(settings, snapshot)
        publisher.publish(snapshot, as_of=date.fromisoformat(as_of), started=started, sidecars=sidecars)
        if deps.forecaster is not None and deps.forecaster.is_fitted:
            FittedStateStore(ArtifactStore(settings)).publish(deps.forecaster.state, run_id=run_id)
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
        if args.ceiling is None:
            args.ceiling = settings.agent_run_ceiling_usd
        if args.ceiling is None:
            # No explicit ceiling means the calendar decides (wolves/run_policy.py).
            fmt = load_format(settings.data_dir)
            args.ceiling = agent_ceiling(settings, fmt, on=datetime.now(UTC).date())
        if args.ceiling <= 0 or args.ceiling > settings.agent_run_ceiling_max_usd:
            parser.error(f"--ceiling must be in (0, {settings.agent_run_ceiling_max_usd:.2f}]")

    sys.exit(asyncio.run(_run(args, settings)))


if __name__ == "__main__":
    main()
