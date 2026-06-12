"""Calendar-aware run policy: each day classifies into a phase and the phase
sets the agent run ceiling. Big group days are days with the focus team, an
Elo top side, a group decider or a packed slate. Days are UTC, matching the
schedule. `python -m wolves.run_policy` prints the derived calendar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from wolves.config import Settings
from wolves.sim.format import FormatData, GroupMatch, load_format
from wolves.sim.ratings import load_elo_ratings

Phase = Literal["rest", "opening", "group", "big_group", "r32_r16", "qf_final"]

_OPENING_DAYS = 7
_BIG_SLATE_GAMES = 6
_LATE_STAGES = {"qf", "sf", "third_place", "final"}


@dataclass(frozen=True)
class DayPolicy:
    on: date
    phase: Phase
    ceiling_usd: float
    big_teams: tuple[str, ...]


def big_team_ids(settings: Settings, fmt: FormatData) -> frozenset[str]:
    """The focus team plus the Elo top sides in the tournament."""
    elo_path = sorted((settings.data_dir / "ratings").glob("elo-2*.tsv"))[-1]
    ratings = load_elo_ratings(elo_path, fmt)
    ranked = sorted(zip(ratings, (team.id for team in fmt.teams), strict=True), reverse=True)
    top = {team_id for _, team_id in ranked[: settings.agent_big_team_count]}
    return frozenset(top | {settings.focus_team})


def _group_games_on(fmt: FormatData, on: date) -> list[GroupMatch]:
    return [m for m in fmt.group_matches if m.date[:10] == on.isoformat()]


def _group_concludes(fmt: FormatData, on: date) -> bool:
    by_group: dict[str, str] = {}
    for m in fmt.group_matches:
        by_group[m.group] = max(by_group.get(m.group, ""), m.date[:10])
    return on.isoformat() in by_group.values() and bool(_group_games_on(fmt, on))


def _games_day_policy(settings: Settings, fmt: FormatData, big: frozenset[str], on: date) -> DayPolicy:
    knockout_games = [m for m in fmt.knockout if m.date[:10] == on.isoformat()]
    knockout_stages = {m.stage for m in knockout_games}
    group_games = _group_games_on(fmt, on)
    playing = {m.home for m in group_games} | {m.away for m in group_games}
    big_playing = tuple(sorted(playing & big))
    # Semis and final are exempt: their single game is the whole stake.
    single_knockout = (
        len(knockout_games) + len(group_games) == 1 and not knockout_stages & {"sf", "final"}
    )

    if knockout_stages & _LATE_STAGES:
        phase: Phase = "qf_final"
        ceiling = settings.agent_ceiling_qf_final_usd
        if single_knockout:
            ceiling = max(ceiling - settings.agent_ceiling_single_game_discount_usd, settings.agent_ceiling_rest_usd)
    elif knockout_stages:
        phase = "r32_r16"
        ceiling = settings.agent_ceiling_r32_r16_usd
        if single_knockout:
            ceiling = max(ceiling - settings.agent_ceiling_single_game_discount_usd, settings.agent_ceiling_rest_usd)
    elif not group_games:
        phase = "rest"
        ceiling = settings.agent_ceiling_rest_usd
    elif on <= _first_group_date(fmt) + timedelta(days=_OPENING_DAYS - 1):
        phase = "opening"
        ceiling = settings.agent_ceiling_opening_usd
    elif big_playing or _group_concludes(fmt, on) or len(group_games) >= _BIG_SLATE_GAMES:
        phase = "big_group"
        ceiling = settings.agent_ceiling_big_group_usd
    else:
        phase = "group"
        ceiling = settings.agent_ceiling_group_usd
    capped = min(ceiling, settings.agent_run_ceiling_max_usd)
    return DayPolicy(on, phase, round(capped, 2), big_playing)


def day_policy(settings: Settings, fmt: FormatData, *, on: date) -> DayPolicy:
    """The morning run digests yesterday evening's games and previews today's,
    so the run date is charged at whichever day is bigger."""
    big = big_team_ids(settings, fmt)
    today = _games_day_policy(settings, fmt, big, on)
    digest = _games_day_policy(settings, fmt, big, on - timedelta(days=1))
    chosen = digest if digest.ceiling_usd > today.ceiling_usd else today
    big_teams = tuple(sorted({*today.big_teams, *digest.big_teams}))
    return DayPolicy(on, chosen.phase, chosen.ceiling_usd, big_teams)


def agent_ceiling(settings: Settings, fmt: FormatData, *, on: date) -> float:
    return day_policy(settings, fmt, on=on).ceiling_usd


def _first_group_date(fmt: FormatData) -> date:
    return date.fromisoformat(min(m.date[:10] for m in fmt.group_matches))


def calendar_dates(fmt: FormatData) -> list[date]:
    stamps = sorted({m.date[:10] for m in fmt.group_matches} | {m.date[:10] for m in fmt.knockout})
    first = date.fromisoformat(stamps[0])
    last = date.fromisoformat(stamps[-1]) + timedelta(days=1)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the derived run-policy calendar")
    parser.parse_args()
    settings = Settings()
    fmt = load_format(settings.data_dir)
    print(f"{'date':<12}{'games':>6}{'phase':>11}{'ceiling':>9}  big teams playing")
    for on in calendar_dates(fmt):
        policy = day_policy(settings, fmt, on=on)
        games = len(_group_games_on(fmt, on)) + sum(1 for m in fmt.knockout if m.date[:10] == on.isoformat())
        print(
            f"{on.isoformat():<12}{games:>6}{policy.phase:>11}{policy.ceiling_usd:>9.2f}  {' '.join(policy.big_teams)}"
        )
    now = datetime.now(UTC).date()
    print(f"\ntoday ({now.isoformat()}): ceiling ${agent_ceiling(settings, fmt, on=now):.2f}")


if __name__ == "__main__":
    main()
