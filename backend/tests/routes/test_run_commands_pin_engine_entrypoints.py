from __future__ import annotations

from wolves_backend.routes.admin import RUN_COMMANDS


def test_run_commands_match_the_workflow_and_ecs_override_contract():
    assert RUN_COMMANDS == {
        "daily": ["wolves.run"],
        "agent": ["wolves.run_agent", "--live", "--confirm-spend"],
    }
