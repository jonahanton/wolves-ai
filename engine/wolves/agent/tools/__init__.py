from wolves.agent.tools import (
    get_odds,
    get_results_and_fixtures,
    ledger_append,
    ledger_query,
    read_journal,
    report_findings,
    run_python,
    run_simulation,
    spawn_researcher,
    submit_forecast,
    web_fetch,
    web_search,
    write_journal,
)
from wolves.agent_tools.core import ToolSpec


def master_toolset() -> list[ToolSpec]:
    return [
        web_search.SPEC,
        web_fetch.SPEC,
        get_odds.SPEC,
        get_results_and_fixtures.SPEC,
        run_simulation.SPEC,
        run_python.SPEC,
        ledger_append.SPEC,
        ledger_query.SPEC,
        read_journal.SPEC,
        write_journal.SPEC,
        spawn_researcher.SPEC,
        submit_forecast.SPEC,
    ]


__all__ = [
    "get_odds",
    "get_results_and_fixtures",
    "ledger_append",
    "ledger_query",
    "master_toolset",
    "read_journal",
    "report_findings",
    "run_python",
    "run_simulation",
    "spawn_researcher",
    "submit_forecast",
    "web_fetch",
    "web_search",
    "write_journal",
]
