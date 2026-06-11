from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from wolves.clients.api_football import MatchFixture, MatchStatus
from wolves.data.contracts import MatchRecord
from wolves.models.contracts import FittedState, ScorelineDistribution
from wolves.models.inmatch import MatchState
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.client import S3UnavailableError
from wolves.s3.layout import LIVE_STATE, LIVE_STATE_POINT
from wolves.sim.format import FormatData, PlayedResult
from wolves.sim.overlay import FixtureResolution, resolve_fixture
from wolves.snapshot import Snapshot

PollStatus = Literal["ok", "failed"]
ForecastSource = Literal["pre_match", "in_match", "settled"]

# Title moves below a hundredth of a percentage point are simulation noise.
_DELTA_FLOOR = 0.0001


class LiveForecast(BaseModel):
    source: ForecastSource
    p_home: float
    p_away: float
    p_draw: float | None = None
    modal_score: str | None = None


class LiveFixture(BaseModel):
    external_id: int
    match: int | None
    status: MatchStatus
    kickoff: str
    city: str | None = None
    minute: int | None = None
    home_id: str | None = None
    away_id: str | None = None
    home_name: str
    away_name: str
    home_goals: int | None = None
    away_goals: int | None = None
    home_reds: int = 0
    away_reds: int = 0
    forecast: LiveForecast | None = None
    message: str | None = None


class LiveState(BaseModel):
    schema_version: int = 1
    generated_at: str
    fetched_at: str
    stale_after: str
    source: str = "api-football"
    poll_status: PollStatus = "ok"
    message: str | None = None
    live_match_count: int = 0
    fixtures: list[LiveFixture] = Field(default_factory=list)
    title_probs: dict[str, float] = Field(default_factory=dict)
    title_deltas_pp: dict[str, float] = Field(default_factory=dict)


class LiveForecaster(Protocol):
    fmt: FormatData

    @property
    def is_fitted(self) -> bool:
        ...

    def fit(self, *, as_of: date | None = None, extra_results: list[MatchRecord] | None = None) -> FittedState:
        ...

    def match_probs(self, home: str, away: str, *, neutral: bool = True, match: int | None = None) -> dict[str, float]:
        ...

    def score_grid(
        self, home: str, away: str, *, neutral: bool = True, match: int | None = None
    ) -> ScorelineDistribution:
        ...

    def live_match(self, home: str, away: str, state: MatchState, *, knockout: bool) -> dict[str, float]:
        ...

    def live_distribution(self, home: str, away: str, state: MatchState) -> ScorelineDistribution:
        ...

    def title_probs(
        self,
        *,
        n_sims: int,
        seed: int = 0,
        results: dict[int, PlayedResult] | None = None,
        live_distributions: dict[int, ScorelineDistribution] | None = None,
    ) -> dict[str, float]:
        ...


class LiveStateStore:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self._artifacts = artifacts

    def load(self) -> LiveState | None:
        body = self._artifacts.get(LIVE_STATE)
        return LiveState.model_validate_json(body) if body else None

    def put(self, state: LiveState) -> None:
        body = state.model_dump_json()
        self._artifacts.put(LIVE_STATE, body)
        if state.poll_status == "failed":
            # An outage at poll cadence would mint thousands of identical history points.
            return
        generated = datetime.fromisoformat(state.generated_at)
        self._artifacts.put(
            LIVE_STATE_POINT,
            body,
            date=generated.date().isoformat(),
            time=generated.strftime("%H%M%S"),
        )

    def record_failure(self, *, message: str, now: datetime | None = None) -> LiveState:
        now = now or datetime.now(UTC)
        # Failure handling must survive a torn file or an S3 outage itself.
        try:
            previous = self.load()
        except (ValidationError, S3UnavailableError):
            previous = None
        if previous is not None:
            state = previous.model_copy(
                update={"generated_at": _stamp(now), "poll_status": "failed", "message": message}
            )
        else:
            state = LiveState(
                generated_at=_stamp(now),
                fetched_at=_stamp(now),
                stale_after=_stamp(now),
                poll_status="failed",
                message=message,
            )
        self.put(state)
        return state


def build_live_state(
    forecaster: LiveForecaster,
    fixtures: list[MatchFixture],
    *,
    fetched_at: datetime,
    results: dict[int, PlayedResult],
    previous: Snapshot | None,
    n_sims: int,
    seed: int = 0,
    stale_after_s: int = 120,
) -> LiveState:
    live_distributions: dict[int, ScorelineDistribution] = {}
    rendered = []
    for fixture in sorted(fixtures, key=lambda f: (f.kickoff, f.fixture_id)):
        resolved = resolve_fixture(forecaster.fmt, fixture)
        distribution: ScorelineDistribution | None = None
        if fixture.status == "live" and resolved is not None:
            state = _match_state(fixture, resolved)
            if state is not None:
                distribution = forecaster.live_distribution(resolved.home_id, resolved.away_id, state)
                live_distributions[resolved.match] = distribution
        rendered.append(_fixture_state(forecaster, fixture, resolved, distribution))

    title_probs = _title_probs(
        forecaster,
        results=results,
        live_distributions=live_distributions,
        n_sims=n_sims,
        seed=seed,
    )
    return LiveState(
        generated_at=_stamp(datetime.now(UTC)),
        fetched_at=_stamp(fetched_at),
        stale_after=_stamp(fetched_at + timedelta(seconds=stale_after_s)),
        live_match_count=sum(1 for fixture in rendered if fixture.status == "live"),
        fixtures=rendered,
        title_probs=title_probs,
        title_deltas_pp=_title_deltas(title_probs, previous),
    )


def _fixture_state(
    forecaster: LiveForecaster,
    fixture: MatchFixture,
    resolved: FixtureResolution | None,
    distribution: ScorelineDistribution | None,
) -> LiveFixture:
    forecast = _forecast(forecaster, fixture, resolved, distribution)
    home_name = _team_name(forecaster.fmt, resolved.home_id) if resolved else fixture.home
    away_name = _team_name(forecaster.fmt, resolved.away_id) if resolved else fixture.away
    return LiveFixture(
        external_id=fixture.fixture_id,
        match=resolved.match if resolved else None,
        status=fixture.status,
        kickoff=fixture.kickoff.isoformat(),
        city=fixture.city,
        minute=fixture.elapsed if fixture.status == "live" else None,
        home_id=resolved.home_id if resolved else None,
        away_id=resolved.away_id if resolved else None,
        home_name=home_name,
        away_name=away_name,
        home_goals=resolved.home_goals if resolved else fixture.home_goals,
        away_goals=resolved.away_goals if resolved else fixture.away_goals,
        home_reds=resolved.home_reds if resolved else fixture.home_reds,
        away_reds=resolved.away_reds if resolved else fixture.away_reds,
        forecast=forecast,
        message=_message(fixture, resolved, forecast),
    )


def _forecast(
    forecaster: LiveForecaster,
    fixture: MatchFixture,
    resolved: FixtureResolution | None,
    distribution: ScorelineDistribution | None,
) -> LiveForecast | None:
    if resolved is None:
        return None
    if fixture.status == "abandoned":
        return None
    if fixture.status == "finished":
        if resolved.home_goals is None or resolved.away_goals is None:
            return None
        return _settled_forecast(fixture, resolved)
    if fixture.status == "live":
        state = _match_state(fixture, resolved)
        if state is None or distribution is None:
            return None
        probs = forecaster.live_match(resolved.home_id, resolved.away_id, state, knockout=resolved.knockout)
        return _forecast_from_probs("in_match", probs, distribution)
    probs = forecaster.match_probs(resolved.home_id, resolved.away_id, match=resolved.match)
    dist = forecaster.score_grid(resolved.home_id, resolved.away_id, match=resolved.match)
    return _forecast_from_probs("pre_match", probs, dist)


def _match_state(fixture: MatchFixture, resolved: FixtureResolution) -> MatchState | None:
    if fixture.elapsed is None or resolved.home_goals is None or resolved.away_goals is None:
        return None
    return MatchState(
        minute=float(fixture.elapsed),
        home_goals=resolved.home_goals,
        away_goals=resolved.away_goals,
        home_reds=resolved.home_reds,
        away_reds=resolved.away_reds,
        period=fixture.period,
    )


def _forecast_from_probs(source: ForecastSource, probs: dict[str, float], dist: ScorelineDistribution) -> LiveForecast:
    return LiveForecast(
        source=source,
        p_home=round(probs["home"], 4),
        p_draw=round(probs["draw"], 4) if "draw" in probs else None,
        p_away=round(probs["away"], 4),
        modal_score=_modal_score(dist),
    )


def _settled_forecast(fixture: MatchFixture, resolved: FixtureResolution) -> LiveForecast | None:
    home_win = resolved.home_goals > resolved.away_goals or (
        resolved.knockout and resolved.home_goals == resolved.away_goals and fixture.winner == "home"
    )
    away_win = resolved.away_goals > resolved.home_goals or (
        resolved.knockout and resolved.home_goals == resolved.away_goals and fixture.winner == "away"
    )
    if resolved.knockout and not home_win and not away_win:
        # Level knockout score without a provider winner: unsettled feed, not a result.
        return None
    return LiveForecast(
        source="settled",
        p_home=1.0 if home_win else 0.0,
        p_draw=1.0 if resolved.home_goals == resolved.away_goals and not resolved.knockout else 0.0,
        p_away=1.0 if away_win else 0.0,
        modal_score=f"{resolved.home_goals}-{resolved.away_goals}",
    )


def _modal_score(dist: ScorelineDistribution) -> str:
    flat = int(dist.grid.argmax())
    side = dist.grid.shape[0]
    return f"{flat // side}-{flat % side}"


def _title_probs(
    forecaster: LiveForecaster,
    *,
    results: dict[int, PlayedResult],
    live_distributions: dict[int, ScorelineDistribution],
    n_sims: int,
    seed: int,
) -> dict[str, float]:
    if not live_distributions:
        return {}
    probs = forecaster.title_probs(
        n_sims=n_sims,
        seed=seed,
        results=results,
        live_distributions=live_distributions,
    )
    return {team: round(prob, 4) for team, prob in probs.items()}


def _title_deltas(title_probs: dict[str, float], previous: Snapshot | None) -> dict[str, float]:
    if not title_probs or previous is None:
        return {}
    baseline = {team.team_id: team.champion_prob for team in previous.teams}
    return {
        team: round((prob - baseline[team]) * 100.0, 2)
        for team, prob in title_probs.items()
        if team in baseline and abs(prob - baseline[team]) >= _DELTA_FLOOR
    }


def _message(fixture: MatchFixture, resolved: FixtureResolution | None, forecast: LiveForecast | None) -> str | None:
    if resolved is None:
        return "fixture is not mapped to the tournament format"
    if fixture.status == "abandoned":
        return "fixture is not active"
    if fixture.status == "live" and forecast is None:
        return "live score is not available yet"
    if fixture.status == "finished" and forecast is None:
        return "result is not settled yet"
    return None


def _team_name(fmt: FormatData, team_id: str) -> str:
    return next((team.name for team in fmt.teams if team.id == team_id), team_id)


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds")
