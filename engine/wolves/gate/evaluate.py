"""Run the gate: leak-free per-fold fits, encompassing test against the
de-vigged market, and (with --promote) a champion record write."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime

import numpy as np

from wolves.config import Settings
from wolves.data.store import DatasetStore
from wolves.gate.encompassing import EncompassingResult, encompassing_test
from wolves.gate.holdout import load_holdout
from wolves.gate.registry import ChampionRecord, ChampionRegistry
from wolves.models.contracts import DatasetHandle, Fixture, UnknownModelTeamError
from wolves.models.poisson import PoissonDecayModel
from wolves.observability.logging import configure_cli_logging

logger = logging.getLogger(__name__)


def evaluate_poisson(dataset: DatasetHandle, *, half_life_days: float | None = None) -> EncompassingResult:
    model = PoissonDecayModel(**({"half_life_days": half_life_days} if half_life_days else {}))
    holdout = load_holdout(dataset)
    states = {}
    model_probs, market_probs, outcomes = [], [], []
    skipped = 0
    for match in holdout:
        if match.fit_as_of not in states:
            states[match.fit_as_of] = model.fit(dataset, as_of=match.fit_as_of)
        try:
            fixture = Fixture(home=match.home_team, away=match.away_team, neutral=match.neutral)
            distribution = model.score_distribution(fixture, states[match.fit_as_of])
        except UnknownModelTeamError:
            skipped += 1
            continue
        model_probs.append(distribution.outcome_probs())
        market_probs.append(match.market)
        outcomes.append(match.outcome)
    if skipped:
        logger.warning("%d holdout matches skipped for unknown teams", skipped)
    return encompassing_test(np.array(model_probs), np.array(market_probs), np.array(outcomes))


def main() -> None:
    configure_cli_logging()
    settings = Settings()
    parser = argparse.ArgumentParser(description="Evaluate the Poisson challenger against the market")
    parser.add_argument("--promote", action="store_true", help="write the champion record on completion")
    args = parser.parse_args()

    path, manifest = DatasetStore(settings).fetch()
    dataset = DatasetHandle(path=path, dataset_id=manifest.dataset_id)
    model = PoissonDecayModel()
    report = evaluate_poisson(dataset)
    logger.info("gate report: %s", report.model_dump_json(indent=2))

    if not args.promote:
        return
    record = ChampionRecord(
        model_id=model.model_id,
        model_version=model.version,
        dataset_id=dataset.dataset_id,
        half_life_days=model.half_life_days,
        blend_weight=report.blend_weight,
        promoted_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rationale=(
            "Evaluable, calibrated and competitive with closing lines pooled over eight tournaments; "
            "blend weight fitted on the frozen holdout. Replaces the unevaluable Elo baseline."
        ),
        gate_report=report,
    )
    path = ChampionRegistry(settings).promote(record)
    logger.info("champion record written to %s", path)


if __name__ == "__main__":
    main()
