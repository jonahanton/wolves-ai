"""In-process deterministic engine: one fitted Forecaster shared by every route.
Engine calls run in worker threads behind a small semaphore so numpy never
blocks the event loop; sims are LRU-cached per fitted state and results set."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from wolves.forecast import Forecaster, ScorelinePerturbation
from wolves.live_state import LiveStateStore
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.fitted import FittedStateStore
from wolves.sim.format import load_results
from wolves.sim.outputs import build_team_reach
from wolves.sim.results_store import played_match_records

if TYPE_CHECKING:
    from collections.abc import Callable

    from wolves.config import Settings as EngineSettings

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


class EngineService:
    """Boots from the published fitted-state artifact, refitting only when absent."""

    def __init__(self, settings: EngineSettings) -> None:
        self._settings = settings
        self._artifacts = ArtifactStore(settings)
        self._fitted_store = FittedStateStore(self._artifacts)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SIMS)
        self._cache: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
        self._forecaster: Forecaster | None = None
        self._fitted_id = ""
        self._results: dict[int, Any] = {}

    @property
    def ready(self) -> bool:
        return self._forecaster is not None

    @property
    def fitted_id(self) -> str:
        return self._fitted_id

    @property
    def forecaster(self) -> Forecaster:
        if self._forecaster is None:
            raise EngineNotReadyError
        return self._forecaster

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
        pointer = self._fitted_store.latest_pointer()
        if pointer is not None:
            state = self._fitted_store.load(run_id=pointer.run_id)
            if state is not None:
                forecaster.restore(state)
                self._fitted_id = pointer.run_id
        if not forecaster.is_fitted:
            forecaster.fit(extra_results=played_match_records(self._settings))
            self._fitted_id = f"local-fit-{forecaster.state.as_of.isoformat()}"
            logger.info("no fitted-state artifact; fitted from the dataset")
        self._results = load_results(self._settings.data_dir, settings=self._settings)
        self._forecaster = forecaster
        logger.info("engine ready: fitted state %s (%s)", self._fitted_id, forecaster.state.model_id)

    async def refresh(self) -> None:
        await asyncio.to_thread(self._refresh)

    def _refresh(self) -> None:
        if self._forecaster is None:
            self._boot()
            return
        pointer = self._fitted_store.latest_pointer()
        results = load_results(self._settings.data_dir, settings=self._settings)
        changed = results != self._results
        if pointer is not None and pointer.run_id != self._fitted_id:
            state = self._fitted_store.load(run_id=pointer.run_id)
            if state is not None:
                self._forecaster.restore(state)
                self._fitted_id = pointer.run_id
                changed = True
                logger.info("engine refreshed to fitted state %s", pointer.run_id)
        if changed:
            self._results = results
            self._cache.clear()

    async def simulate_pins(self, pins: list[Pin], *, n_sims: int, seed: int) -> dict[str, Any]:
        """CRN-paired baseline and pinned reach probabilities from one fitted state."""
        if self._forecaster is None:
            raise EngineNotReadyError
        for pin in pins:
            if pin.match in self._results:
                raise MatchAlreadyPlayedError(pin.match)
        pinned_key = tuple(sorted((p.match, p.home_goals, p.away_goals) for p in pins))
        baseline = await self._cached(
            ("reach", self._fitted_id, (), n_sims, seed), lambda: self._reach((), n_sims, seed)
        )
        pinned = (
            await self._cached(
                ("reach", self._fitted_id, pinned_key, n_sims, seed), lambda: self._reach(pins, n_sims, seed)
            )
            if pins
            else baseline
        )
        return {
            "engine": self._engine_block(n_sims=n_sims, seed=seed),
            "baseline": baseline,
            "pinned": pinned,
        }

    async def match_grid(self, match: int) -> dict[str, Any]:
        forecaster = self.forecaster
        return await self._cached(("grid", self._fitted_id, match), lambda: self._grid(forecaster, match))

    def _engine_block(self, *, n_sims: int, seed: int) -> dict[str, Any]:
        state = self.forecaster.state
        return {
            "fitted_run_id": self._fitted_id,
            "model_id": state.model_id,
            "as_of": state.as_of.isoformat(),
            "n_sims": n_sims,
            "seed": seed,
        }

    def _reach(self, pins: list[Pin] | tuple[()], n_sims: int, seed: int) -> dict[str, dict[str, float]]:
        forecaster = self.forecaster
        perturbations = tuple(
            ScorelinePerturbation(match=p.match, home_goals=p.home_goals, away_goals=p.away_goals, reason="api pin")
            for p in pins
        )
        result = forecaster.simulate(
            n_sims=n_sims,
            seed=seed,
            perturbations=perturbations,
            results=self._results,
            parameter_uncertainty=False,
        )
        return build_team_reach(forecaster.fmt, result)

    def _grid(self, forecaster: Forecaster, match: int) -> dict[str, Any]:
        home, away, stage = self._fixture_teams(forecaster, match)
        grid = forecaster.score_grid(home, away, match=match)
        return {
            "match": match,
            "stage": stage,
            "home_id": home,
            "away_id": away,
            "grid": [[round(float(p), 5) for p in row] for row in grid.grid],
            "p_home": round(grid.p_home, 4),
            "p_draw": round(grid.p_draw, 4),
            "p_away": round(grid.p_away, 4),
            "fitted_run_id": self._fitted_id,
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

    async def _cached(self, key: tuple[Any, ...], compute: Callable[[], Any]) -> Any:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        async with self._semaphore:
            value = await asyncio.to_thread(compute)
        self._cache[key] = value
        if len(self._cache) > SIM_CACHE_SIZE:
            self._cache.popitem(last=False)
        return value
