"""Calendar-aware run policy: the agent run ceiling scales with how much the
tournament moved yesterday and how much knockout money is on the table today.
Days are UTC, matching the schedule. `python -m wolves.run_policy` prints the
derived calendar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from wolves.clients.odds.team_names import team_id_for_name
from wolves.config import Settings
from wolves.sim.format import FormatData, load_format

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wolves.clients.api_football import MatchFixture

_STAGE_WEIGHTS = {
    "group": 1.0,
    "r32": 1.5,
    "r16": 2.0,
    "qf": 2.5,
    "sf": 3.0,
    "third_place": 1.5,
    "final": 4.0,
}


@dataclass(frozen=True)
class DayPolicy:
    on: date
    results_weight: float
    knockout_weight: float
    focus_involved: bool
    ceiling_usd: float


def _games_on(fmt: FormatData, on: date) -> list[tuple[str, str, str]]:
    day = on.isoformat()
    group = [("group", m.home, m.away) for m in fmt.group_matches if m.date[:10] == day]
    knockout = [(m.stage, m.home, m.away) for m in fmt.knockout if m.date[:10] == day]
    return group + knockout


def _focus_involved(
    fmt: FormatData, settings: Settings, days: tuple[date, date], fixtures: Sequence[MatchFixture]
) -> bool:
    stamps = {d.isoformat() for d in days}
    if any(m.date[:10] in stamps and settings.focus_team in (m.home, m.away) for m in fmt.group_matches):
        return True
    # Knockout pairings are slot specs in the schedule; once the bracket is
    # set the provider fixtures carry the real names.
    for fixture in fixtures:
        if fixture.kickoff.astimezone(UTC).date().isoformat() not in stamps:
            continue
        if settings.focus_team in (
            team_id_for_name(fixture.home, fmt.teams),
            team_id_for_name(fixture.away, fmt.teams),
        ):
            return True
    return False


def day_policy(settings: Settings, fmt: FormatData, *, on: date, fixtures: Sequence[MatchFixture] = ()) -> DayPolicy:
    yesterday = _games_on(fmt, on - timedelta(days=1))
    knockout_today = [g for g in _games_on(fmt, on) if g[0] != "group"]
    focus = _focus_involved(fmt, settings, (on - timedelta(days=1), on), fixtures)
    results_weight = sum(_STAGE_WEIGHTS[stage] for stage, _, _ in yesterday)
    knockout_weight = sum(_STAGE_WEIGHTS[stage] for stage, _, _ in knockout_today)
    if not yesterday and not knockout_today:
        return DayPolicy(on, 0.0, 0.0, focus, round(settings.agent_ceiling_rest_day_usd, 2))
    ceiling = (
        settings.agent_ceiling_base_usd
        + results_weight * settings.agent_ceiling_per_result_usd
        + knockout_weight * settings.agent_ceiling_knockout_today_usd
        + (settings.agent_ceiling_focus_bonus_usd if focus else 0.0)
    )
    capped = min(ceiling, settings.agent_ceiling_policy_max_usd, settings.agent_run_ceiling_max_usd)
    return DayPolicy(on, results_weight, knockout_weight, focus, round(capped, 2))


def agent_ceiling(settings: Settings, fmt: FormatData, *, on: date, fixtures: Sequence[MatchFixture] = ()) -> float:
    return day_policy(settings, fmt, on=on, fixtures=fixtures).ceiling_usd


def _calendar_dates(fmt: FormatData) -> list[date]:
    stamps = sorted({m.date[:10] for m in fmt.group_matches} | {m.date[:10] for m in fmt.knockout})
    first = date.fromisoformat(stamps[0])
    last = date.fromisoformat(stamps[-1]) + timedelta(days=1)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the derived run-policy calendar")
    parser.parse_args()
    settings = Settings()
    fmt = load_format(settings.data_dir)
    print(f"{'date':<12}{'games':>6}{'ko today':>9}{'focus':>7}{'ceiling':>9}  kickoffs (UTC)")
    for on in _calendar_dates(fmt):
        policy = day_policy(settings, fmt, on=on)
        today = _games_on(fmt, on)
        kickoffs = sorted(
            {m.date[11:16] for m in fmt.group_matches if m.date[:10] == on.isoformat()}
            | {m.date[11:16] for m in fmt.knockout if m.date[:10] == on.isoformat()}
        )
        focus = "yes" if policy.focus_involved else ""
        print(
            f"{on.isoformat():<12}{len(today):>6}{policy.knockout_weight:>9.1f}{focus:>7}"
            f"{policy.ceiling_usd:>9.2f}  {' '.join(kickoffs)}"
        )
    now = datetime.now(UTC).date()
    print(f"\ntoday ({now.isoformat()}): ceiling ${agent_ceiling(settings, fmt, on=now):.2f}")


if __name__ == "__main__":
    main()
