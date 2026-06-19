from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel

from wolves.agent.deps import AgentDeps
from wolves.sim.format import GROUPS, FormatData, GroupMatch, PlayedResult, load_format
from wolves.sim.overlay import resolve_fixture, results_from_fixtures
from wolves.toolkit._timeout import run_with_timeout
from wolves.toolkit.core import ToolSpec
from wolves.toolkit.result import ToolError, ToolResult


class GetResultsAndFixturesArgs(BaseModel):
    date: str | None = None


def _invalid_date(message: str) -> ToolResult[Any]:
    return ToolResult(ok=False, payload=None, error=ToolError(type="invalid_arguments", message=message))


def _team_lookup(fmt: FormatData) -> dict[str, str]:
    return {team.id: team.name for team in fmt.teams}


def _group_match_lookup(fmt: FormatData) -> dict[int, GroupMatch]:
    return {match.match: match for match in fmt.group_matches}


def _points(home_goals: int, away_goals: int) -> tuple[int, int]:
    if home_goals > away_goals:
        return 3, 0
    if away_goals > home_goals:
        return 0, 3
    return 1, 1


def _empty_group_rows(fmt: FormatData) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        group: {
            team.id: {"team_id": team.id, "team": team.name, "played": 0, "points": 0, "gf": 0, "ga": 0, "gd": 0}
            for team in fmt.teams
            if team.group == group
        }
        for group in GROUPS
    }


def _group_tables(fmt: FormatData, played: dict[int, PlayedResult]) -> list[dict[str, Any]]:
    matches = _group_match_lookup(fmt)
    rows = _empty_group_rows(fmt)
    for match_no, result in sorted(played.items()):
        match = matches.get(match_no)
        if match is None:
            continue
        home = rows[match.group][match.home]
        away = rows[match.group][match.away]
        home_points, away_points = _points(result.home_goals, result.away_goals)
        home["played"] += 1
        away["played"] += 1
        home["points"] += home_points
        away["points"] += away_points
        home["gf"] += result.home_goals
        home["ga"] += result.away_goals
        away["gf"] += result.away_goals
        away["ga"] += result.home_goals
        home["gd"] = home["gf"] - home["ga"]
        away["gd"] = away["gf"] - away["ga"]
    return [
        {
            "group": group,
            "teams": sorted(table.values(), key=lambda row: (-row["points"], -row["gd"], -row["gf"], row["team"])),
        }
        for group, table in rows.items()
    ]


def _enriched_matches(fmt: FormatData, matches: list[Any]) -> list[dict[str, Any]]:
    names = _team_lookup(fmt)
    group_matches = _group_match_lookup(fmt)
    enriched: list[dict[str, Any]] = []
    for fixture in matches:
        item = fixture.model_dump(mode="json")
        resolved = resolve_fixture(fmt, fixture)
        if resolved is None:
            item["resolved"] = False
            enriched.append(item)
            continue
        group_match = group_matches.get(resolved.match)
        item.update(
            {
                "resolved": True,
                "match": resolved.match,
                "stage": "group" if group_match is not None else "knockout",
                "group": group_match.group if group_match is not None else None,
                "home_id": resolved.home_id,
                "away_id": resolved.away_id,
                "home_team": names.get(resolved.home_id, resolved.home_id),
                "away_team": names.get(resolved.away_id, resolved.away_id),
                "home_goals": resolved.home_goals,
                "away_goals": resolved.away_goals,
            }
        )
        enriched.append(item)
    return enriched


def _fixture_on(fixture: Any, day: str | None) -> bool:
    return day is None or fixture.kickoff.date().isoformat() == day


def _fixture_at_or_before(fixture: Any, day: str | None) -> bool:
    return not day or fixture.kickoff.date() <= date.fromisoformat(day)


async def _get_results_and_fixtures(args: GetResultsAndFixturesArgs, deps: AgentDeps) -> ToolResult[Any]:
    if args.date and deps.as_of:
        try:
            requested = date.fromisoformat(args.date)
            today = date.fromisoformat(deps.as_of)
        except ValueError:
            return _invalid_date(f"date {args.date} must be YYYY-MM-DD; today is {deps.as_of}")
        if requested.year != today.year:
            return _invalid_date(f"date {args.date} is outside this tournament; today is {deps.as_of}")
        if requested > today:
            return _invalid_date(
                f"date {args.date} is after today {deps.as_of}; do not query live fixture state after as-of"
            )
    deps.runtime.charge_data_fetch()
    with deps.runtime.observe(kind="data_fetch", actor=deps.actor, name="get_results_and_fixtures") as rec:
        fmt = load_format(deps.settings.data_dir)
        all_matches = await run_with_timeout(
            deps.fixtures.fixtures(date=None),
            tool_name="get_results_and_fixtures",
            timeout_seconds=deps.settings.tool_timeout_seconds,
        )
        matches = [match for match in all_matches if _fixture_on(match, args.date)]
        standings_matches = [match for match in all_matches if _fixture_at_or_before(match, deps.as_of)]
        rec.set_output({"matches": len(matches)})
        rec.note(summary=f"fixtures{f' on {args.date}' if args.date else ''}: {len(matches)} match(es)")
    played = results_from_fixtures(fmt, standings_matches)
    return ToolResult(
        payload={
            "matches": _enriched_matches(fmt, matches),
            "group_tables_scope": f"all known fixtures through {deps.as_of}" if deps.as_of else "all known fixtures",
            "group_tables": _group_tables(fmt, played),
            "groups": [
                {
                    "group": group,
                    "teams": [{"team_id": team.id, "team": team.name} for team in fmt.teams if team.group == group],
                }
                for group in GROUPS
            ],
        }
    )


SPEC = ToolSpec(
    name="get_results_and_fixtures",
    description=(
        "Structured tournament state from API-Football plus the canonical World Cup format: played results, "
        "live scores, upcoming fixtures, resolved match ids, groups and group tables. Pass a YYYY-MM-DD date "
        "to narrow fixture rows to one day; calls are rate-limited, so batch by date."
    ),
    args_model=GetResultsAndFixturesArgs,
    fn=_get_results_and_fixtures,
)
