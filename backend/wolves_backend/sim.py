"""One fitted Forecaster for every route: thread-pooled behind a semaphore, LRU-cached."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from wolves.forecast import Forecaster, ScorelinePerturbation
from wolves.insights.explain import model_explain
from wolves.insights.market_gaps import market_gaps
from wolves.insights.path_tree import team_path_tree
from wolves.live_state import LiveStateStore
from wolves.run_policy import calendar_dates, day_policy
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.fitted import FittedStateStore
from wolves.s3.layout import ODDS_SNAPSHOT
from wolves.sim.format import load_results
from wolves.sim.outputs import build_team_reach
from wolves.sim.results_store import played_match_records

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date
    from pathlib import Path

    from wolves.config import Settings as EngineSettings
    from wolves.insights.explain import StrengthExplanation
    from wolves.insights.market_gaps import MarketGaps
    from wolves.insights.path_tree import PathTree
    from wolves.run_policy import DayPolicy
    from wolves.sim.format import FormatData, PlayedResult

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SIMS = 2
SIM_CACHE_SIZE = 128


class EngineNotReadyError(Exception):
    def __init__(self) -> None:
        super().__init__("the engine has no fitted state yet")


class MatchAlreadyPlayedError(Exception):
    def __init__(self, match: int) -> None:
        self.match = match
        super().__init__(f"match {match} has a final result; it cannot be pinned")


class MatchTeamsUnknownError(Exception):
    def __init__(self, match: int) -> None:
        self.match = match
        super().__init__(f"match {match} has no resolved teams yet")


class Pin:
    __slots__ = ("away_goals", "home_goals", "match")

    def __init__(self, *, match: int, home_goals: int, away_goals: int) -> None:
        self.match = match
        self.home_goals = home_goals
        self.away_goals = away_goals


@dataclass(frozen=True)
class _Fit:
    """One immutable serving state; requests snapshot it so a refresh mid-sim cannot mix states."""

    forecaster: Forecaster
    fitted_id: str
    results: dict[int, PlayedResult]
    revision: int


def match_dates(fmt: FormatData) -> dict[int, str]:
    """Scheduled ISO date per match number, group and knockout alike."""
    dates = {m.match: m.date for m in fmt.group_matches}
    dates.update({m.match: m.date for m in fmt.knockout})
    return dates


class EngineService:
    """Boots from the published fitted-state artifact, refitting only when absent."""

    def __init__(self, settings: EngineSettings) -> None:
        self._settings = settings
        self._artifacts = ArtifactStore(settings)
        self._fitted_store = FittedStateStore(self._artifacts)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SIMS)
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._fit: _Fit | None = None

    @property
    def ready(self) -> bool:
        return self._fit is not None

    @property
    def settings(self) -> EngineSettings:
        return self._settings

    @property
    def fitted_id(self) -> str:
        return self._snapshot().fitted_id

    @property
    def forecaster(self) -> Forecaster:
        return self._snapshot().forecaster

    def _snapshot(self) -> _Fit:
        fit = self._fit
        if fit is None:
            raise EngineNotReadyError
        return fit

    async def run(self, *, refresh_interval_s: float) -> None:
        """Boot, then keep the fitted state aligned with the published pointer."""
        try:
            await self.boot()
        except Exception:
            logger.exception("engine boot failed; engine routes unavailable until a refresh succeeds")
        while True:
            await asyncio.sleep(refresh_interval_s)
            try:
                await self.refresh()
            except Exception:
                logger.exception("engine refresh failed")

    async def boot(self) -> None:
        await asyncio.to_thread(self._boot)

    def _boot(self) -> None:
        forecaster = Forecaster(self._settings)
        fitted_id = ""
        pointer = self._fitted_store.latest_pointer()
        if pointer is not None:
            state = self._fitted_store.load(run_id=pointer.run_id)
            if state is not None:
                forecaster.restore(state)
                fitted_id = pointer.run_id
        if not forecaster.is_fitted:
            forecaster.fit(extra_results=played_match_records(self._settings))
            fitted_id = f"local-fit-{forecaster.state.as_of.isoformat()}"
            logger.info("no fitted-state artifact; fitted from the dataset")
        results = load_results(self._settings.data_dir, settings=self._settings)
        with self._lock:
            revision = self._fit.revision + 1 if self._fit else 0
            self._fit = _Fit(forecaster, fitted_id, results, revision)
        logger.info("engine ready: fitted state %s (%s)", fitted_id, forecaster.state.model_id)

    async def refresh(self) -> None:
        await asyncio.to_thread(self._refresh)

    def _refresh(self) -> None:
        fit = self._fit
        if fit is None:
            self._boot()
            return
        pointer = self._fitted_store.latest_pointer()
        results = load_results(self._settings.data_dir, settings=self._settings)
        forecaster, fitted_id = fit.forecaster, fit.fitted_id
        if pointer is not None and pointer.run_id != fit.fitted_id:
            state = self._fitted_store.load(run_id=pointer.run_id)
            if state is not None:
                forecaster = Forecaster(self._settings)
                forecaster.restore(state)
                fitted_id = pointer.run_id
                logger.info("engine refreshed to fitted state %s", pointer.run_id)
        if fitted_id == fit.fitted_id and results == fit.results:
            return
        with self._lock:
            self._fit = _Fit(forecaster, fitted_id, results, fit.revision + 1)

    async def simulate_pins(
        self, pins: list[Pin], *, n_sims: int, seed: int, results_until: str | None = None
    ) -> dict[str, Any]:
        """CRN-paired baseline and pinned reach probabilities from one fitted state."""
        fit = self._snapshot()
        for pin in pins:
            if pin.match in fit.results:
                raise MatchAlreadyPlayedError(pin.match)
        baseline = await self._reach_cached(fit, (), n_sims=n_sims, seed=seed, results_until=results_until)
        pinned = (
            await self._reach_cached(fit, pins, n_sims=n_sims, seed=seed, results_until=results_until)
            if pins
            else baseline
        )
        return {
            "engine": self._engine_block(fit, n_sims=n_sims, seed=seed),
            "baseline": baseline,
            "pinned": pinned,
        }

    async def played_results(self) -> list[dict[str, Any]]:
        """Final scores joined with the schedule, newest first."""
        fit = self._snapshot()
        return await self._cached(("results", fit.revision), lambda: self._played(fit))

    async def scores_hold(self, held: list[Pin], *, n_sims: int, seed: int = 0) -> dict[str, Any]:
        """Champion-probability deltas if every in-play score becomes the final one."""
        fit = self._snapshot()
        baseline = await self._reach_cached(fit, (), n_sims=n_sims, seed=seed)
        held_reach = await self._reach_cached(fit, held, n_sims=n_sims, seed=seed)
        base = {team: reach["champion"] for team, reach in baseline.items()}
        hold = {team: reach["champion"] for team, reach in held_reach.items()}
        return {
            "fitted_run_id": fit.fitted_id,
            "n_sims": n_sims,
            "baseline": base,
            "held": hold,
            "deltas_pp": {team: round((hold[team] - base[team]) * 100.0, 2) for team in base},
        }

    async def match_grid(self, match: int) -> dict[str, Any]:
        fit = self._snapshot()
        return await self._cached(("grid", fit.revision, match), lambda: self._grid(fit, match))

    async def team_paths(self, team: str, *, view: Literal["reach", "title"]) -> PathTree:
        fit = self._snapshot()
        self._require_team(fit.forecaster, team)
        n_sims = self._settings.publish_n_sims
        return await self._cached(
            ("paths", fit.revision, team, view, n_sims),
            lambda: team_path_tree(fit.forecaster, team, view=view, results=fit.results, n_sims=n_sims),
        )

    async def team_explain(self, team: str) -> StrengthExplanation:
        fit = self._snapshot()
        self._require_team(fit.forecaster, team)
        return await self._cached(("explain", fit.revision, team), lambda: model_explain(fit.forecaster, team))

    async def market_gaps(self) -> MarketGaps:
        fit = self._snapshot()
        archive_dir = self._settings.runs_root / ODDS_SNAPSHOT.prefix
        marker = await asyncio.to_thread(self._latest_series_marker, archive_dir)
        n_sims = self._settings.publish_n_sims
        return await self._cached(
            ("market-gaps", fit.revision, marker, n_sims),
            lambda: market_gaps(fit.forecaster, archive_dir, results=fit.results, n_sims=n_sims),
        )

    async def run_policy(self) -> dict[str, Any]:
        fit = self._snapshot()
        today = datetime.now(UTC).date()
        return await self._cached(
            ("run-policy", fit.revision, today.isoformat()), lambda: self._run_policy(fit.forecaster, today)
        )

    async def _reach_cached(
        self, fit: _Fit, pins: list[Pin] | tuple[()], *, n_sims: int, seed: int, results_until: str | None = None
    ) -> dict[str, dict[str, float]]:
        pin_key = tuple(sorted((p.match, p.home_goals, p.away_goals) for p in pins))
        key = ("reach", fit.revision, pin_key, n_sims, seed, results_until)
        return await self._cached(key, lambda: self._reach(fit, pins, n_sims, seed, results_until))

    def _run_policy(self, forecaster: Forecaster, today: date) -> dict[str, Any]:
        fmt = forecaster.fmt
        policies = [day_policy(self._settings, fmt, on=on) for on in calendar_dates(fmt)]
        chosen = day_policy(self._settings, fmt, on=today)
        return {"today": self._policy_block(chosen), "calendar": [self._policy_block(p) for p in policies]}

    @staticmethod
    def _policy_block(policy: DayPolicy) -> dict[str, Any]:
        return {
            "date": policy.on.isoformat(),
            "phase": policy.phase,
            "ceiling_usd": policy.ceiling_usd,
            "big_teams": list(policy.big_teams),
        }

    @staticmethod
    def _require_team(forecaster: Forecaster, team: str) -> None:
        if team not in {t.id for t in forecaster.fmt.teams}:
            raise KeyError(team)

    @staticmethod
    def _latest_series_marker(archive_dir: Path) -> str:
        names = sorted(archive_dir.glob("*/*.series.json"))
        return names[-1].name if names else ""

    @staticmethod
    def _engine_block(fit: _Fit, *, n_sims: int, seed: int) -> dict[str, Any]:
        state = fit.forecaster.state
        return {
            "fitted_run_id": fit.fitted_id,
            "model_id": state.model_id,
            "as_of": state.as_of.isoformat(),
            "n_sims": n_sims,
            "seed": seed,
        }

    def _reach(
        self, fit: _Fit, pins: list[Pin] | tuple[()], n_sims: int, seed: int, results_until: str | None
    ) -> dict[str, dict[str, float]]:
        perturbations = tuple(
            ScorelinePerturbation(match=p.match, home_goals=p.home_goals, away_goals=p.away_goals, reason="api pin")
            for p in pins
        )
        results = fit.results
        if results_until is not None:
            dates = match_dates(fit.forecaster.fmt)
            results = {m: r for m, r in results.items() if dates.get(m, "") <= results_until}
        result = fit.forecaster.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            results=results,
            parameter_uncertainty=False,
        )
        return build_team_reach(fit.forecaster.fmt, result)

    def _played(self, fit: _Fit) -> list[dict[str, Any]]:
        fmt = fit.forecaster.fmt
        dates = match_dates(fmt)
        group_teams = {m.match: (m.home, m.away) for m in fmt.group_matches}
        stages = {m.match: m.stage for m in fmt.knockout}
        live = LiveStateStore(self._artifacts).load()
        live_teams = (
            {f.match: (f.home_id, f.away_id) for f in live.fixtures if f.match is not None} if live is not None else {}
        )
        rows = []
        for match, result in fit.results.items():
            home_id, away_id = group_teams.get(match) or live_teams.get(match) or (None, None)
            rows.append(
                {
                    "match": match,
                    "date": dates.get(match, ""),
                    "stage": stages.get(match, "group"),
                    "home_id": home_id,
                    "away_id": away_id,
                    "home_goals": result.home_goals,
                    "away_goals": result.away_goals,
                    "winner": result.winner,
                }
            )
        rows.sort(key=lambda row: (row["date"], row["match"]), reverse=True)
        return rows

    def _grid(self, fit: _Fit, match: int) -> dict[str, Any]:
        home, away, stage = self._fixture_teams(fit.forecaster, match)
        grid = fit.forecaster.score_grid(home, away, match=match)
        return {
            "match": match,
            "stage": stage,
            "home_id": home,
            "away_id": away,
            "grid": [[round(float(p), 5) for p in row] for row in grid.grid],
            "p_home": round(grid.p_home, 4),
            "p_draw": round(grid.p_draw, 4),
            "p_away": round(grid.p_away, 4),
            "fitted_run_id": fit.fitted_id,
        }

    def _fixture_teams(self, forecaster: Forecaster, match: int) -> tuple[str, str, str]:
        for m in forecaster.fmt.group_matches:
            if m.match == match:
                return m.home, m.away, "group"
        spec = next((m for m in forecaster.fmt.knockout if m.match == match), None)
        if spec is None:
            raise KeyError(match)
        state = LiveStateStore(self._artifacts).load()
        if state is not None:
            for fixture in state.fixtures:
                if fixture.match == match and fixture.home_id and fixture.away_id:
                    return fixture.home_id, fixture.away_id, spec.stage
        raise MatchTeamsUnknownError(match)

    async def run_blocking(self, fn: Callable[[], Any]) -> Any:
        """Run one engine-heavy callable on a worker thread behind the sim semaphore."""
        async with self._semaphore:
            return await asyncio.to_thread(fn)

    async def _cached(self, key: tuple[Any, ...], compute: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        value = await self.run_blocking(compute)
        with self._lock:
            self._cache[key] = value
            if len(self._cache) > SIM_CACHE_SIZE:
                self._cache.popitem(last=False)
        return value
