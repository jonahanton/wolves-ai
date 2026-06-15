from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from wolves.agent.continuity import build_previous_run_digest
from wolves.agent.deps import AgentDeps
from wolves.agent.scoring import latest_snapshot_by_kind
from wolves.graph.artifacts import RunArtifactStore
from wolves.graph.contracts import NodeOutcome
from wolves.insights.what_changed import diff_inputs
from wolves.snapshot import Snapshot, run_day

CoverageLevel = Literal["none_seen", "light_suggested", "standard_suggested"]


class ResearchCoverageSignals(BaseModel):
    previous_run_id: str | None = None
    scratch_run: bool = False
    days_since_previous: int | None = None
    hours_since_previous: float | None = None
    previous_web_searches: int | None = None
    previous_retrieval_artifacts: int | None = None
    played_results_since_previous: int = 0
    market_moves_since_previous: int = 0
    upcoming_fixtures_48h: int = 0
    open_scenarios: int = 0


class ResearchCoverageHint(BaseModel):
    level: CoverageLevel
    reasons: list[str] = Field(default_factory=list)
    lanes: list[str] = Field(default_factory=list)
    signals: ResearchCoverageSignals = Field(default_factory=ResearchCoverageSignals)

    def digest(self) -> str:
        lanes = ", ".join(self.lanes) if self.lanes else "master judgement"
        reasons = "; ".join(self.reasons) if self.reasons else "no deterministic cue fired"
        return (
            f"Research coverage hint: {self.level}. Reasons: {reasons}. Suggested lanes: {lanes}. "
            "This is advisory: deterministic cues can miss public developments, so still ask what could be missing."
        )


def research_coverage_hint(deps: AgentDeps, *, as_of: str) -> ResearchCoverageHint:
    previous = _previous_agent(deps, as_of=as_of)
    signals = ResearchCoverageSignals(
        previous_run_id=previous.run.run_id if previous is not None else None,
        scratch_run=deps.disable_continuity,
    )
    reasons: list[str] = []
    lanes = [
        "structured state",
        "contender ambient scan",
        "market disagreement scan",
        "open-ended material developments",
    ]
    if previous is None:
        return ResearchCoverageHint(
            level="standard_suggested",
            reasons=["no previous agent forecast is available"],
            lanes=lanes,
            signals=signals,
        )
    today = date.fromisoformat(as_of)
    previous_day = date.fromisoformat(run_day(previous.run))
    signals.days_since_previous = max(0, (today - previous_day).days)
    signals.hours_since_previous = _hours_since(previous.run.created_at, as_of=as_of)
    if signals.hours_since_previous is not None and signals.hours_since_previous >= 18:
        reasons.append(f"previous agent forecast is {signals.hours_since_previous:.0f} hours old")
    elif signals.days_since_previous >= 2:
        reasons.append(f"previous agent forecast is {signals.days_since_previous} days old")
    digest = build_previous_run_digest(previous, settings=deps.settings)
    signals.previous_web_searches = digest.events.web_searches if digest.events_available else None
    signals.previous_retrieval_artifacts = (
        digest.artifacts.counts.get("retrieval") if digest.artifact_index_available else None
    )
    if signals.previous_web_searches is not None and signals.previous_web_searches <= 1:
        reasons.append("previous run had very thin web research")
    if signals.previous_retrieval_artifacts is not None and signals.previous_retrieval_artifacts <= 1:
        reasons.append("previous run left few retrieval artifacts")
    played, market_moves, fixtures = diff_inputs(
        previous=previous,
        forecaster=deps.forecaster,
        archive_dir=deps.settings.runs_root / "odds-archive",
        as_of=as_of,
        move_floor_pp=deps.settings.market_movement_noise_floor_pp,
    )
    signals.played_results_since_previous = len(played)
    signals.market_moves_since_previous = len(market_moves)
    signals.upcoming_fixtures_48h = len(fixtures)
    if played:
        reasons.append(f"{len(played)} tournament result(s) landed since the previous agent forecast")
        lanes.append("result aftermath scan")
    if market_moves:
        reasons.append(f"{len(market_moves)} market move(s) cleared the noise floor")
    if fixtures:
        lanes.append("imminent high-leverage fixture scan")
    if deps.scenarios is not None:
        signals.open_scenarios = len([scenario for scenario in deps.scenarios.open_scenarios() if scenario.weight > 0])
        if signals.open_scenarios:
            reasons.append(f"{signals.open_scenarios} open scenario(s) need lifecycle audit")
    if not reasons:
        return ResearchCoverageHint(level="none_seen", lanes=["open-ended material developments"], signals=signals)
    level: CoverageLevel = "standard_suggested" if _standard(signals) else "light_suggested"
    return ResearchCoverageHint(level=level, reasons=reasons, lanes=_dedupe(lanes), signals=signals)


def research_coverage_brief(hint: ResearchCoverageHint, *, as_of: str) -> str:
    return (
        f"For forecast date {as_of}, perform the advisory research coverage scan before the master plans the day. "
        f"{hint.digest()} Use first-party structured tools first. Do not search private ids. "
        "If the boundary is date-only, be conservative about same-day material: do not cite reports, line-ups, "
        "odds moves or reactions unless the brief or fetched source makes them clearly knowable by the intended "
        "run time. If you use web search, consider a semantic source-discovery search with provider='exa', no "
        "freshness, when broader tournament or contender context might explain market or world-shape questions; "
        "if Exa returns stale or generic material, switch to Brave, cached sources or structured tools. Use Brave "
        "for freshness-bound news. Use at most four concise web searches total, rank candidates in one batch if "
        "web search is used, and fetch only sources that can change a forecast decision. Cover the suggested lanes "
        "without letting availability or injuries dominate unless they are genuinely the material story. Include "
        "one open-ended search for material World Cup developments not named by the deterministic cues when this "
        "scan needs broad public coverage. Put any candidate forecast-world branches your research surfaced in "
        "candidate_branches; put plausible branches you checked but found unsupported in signals. Do not assume a "
        "market disagreement needs a public headline; no named catalyst found is a useful signal for quant, not a "
        "failed search. Return typed evidence only for load-bearing public facts; otherwise put checked, "
        "immaterial or negative findings in signals."
    )


def add_research_coverage_receipt(
    store: RunArtifactStore,
    *,
    hint: ResearchCoverageHint,
    outcome: NodeOutcome | None = None,
) -> str:
    payload = {"hint": hint.model_dump(mode="json")}
    if outcome is not None:
        payload["seeded_research"] = outcome.model_dump(mode="json")
    artifact = store.add(
        kind="report",
        created_by="runner",
        summary=f"research coverage {hint.level}: {'; '.join(hint.reasons)[:120] or 'no cue fired'}",
        payload=payload,
    )
    return artifact.id


def should_seed_research(hint: ResearchCoverageHint) -> bool:
    signals = hint.signals
    if signals.previous_run_id is None:
        return bool(signals.scratch_run and hint.level == "standard_suggested")
    return bool(
        signals.previous_run_id
        and hint.level in {"light_suggested", "standard_suggested"}
        and (
            (signals.days_since_previous or 0) >= 2
            or (signals.hours_since_previous or 0) >= 18
            or _thin_previous_research(signals)
            or signals.played_results_since_previous > 0
            or signals.market_moves_since_previous > 0
        )
    )


def _previous_agent(deps: AgentDeps, *, as_of: str) -> Snapshot | None:
    if deps.disable_continuity:
        return None
    return latest_snapshot_by_kind(
        deps.settings.runs_root / "snapshots",
        before=date.fromisoformat(as_of),
        kind="agent",
    )


def _standard(signals: ResearchCoverageSignals) -> bool:
    return (
        (signals.days_since_previous or 0) >= 2
        or (signals.hours_since_previous or 0) >= 36
        or _thin_previous_research(signals)
        or signals.played_results_since_previous >= 2
        or signals.market_moves_since_previous >= 2
    )


def _thin_previous_research(signals: ResearchCoverageSignals) -> bool:
    return bool(
        (signals.previous_web_searches is not None and signals.previous_web_searches <= 1)
        or (signals.previous_retrieval_artifacts is not None and signals.previous_retrieval_artifacts <= 1)
    )


def _hours_since(created_at: str, *, as_of: str) -> float | None:
    try:
        previous = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=UTC)
    boundary = _current_boundary(as_of)
    return max(0.0, (boundary - previous).total_seconds() / 3600)


def _current_boundary(as_of: str) -> datetime:
    try:
        day = date.fromisoformat(as_of)
    except ValueError:
        return datetime.now(UTC)
    today = datetime.now(UTC).date()
    if day == today:
        return datetime.now(UTC)
    return datetime.combine(day, time.max, tzinfo=UTC)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
