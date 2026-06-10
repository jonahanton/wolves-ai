from __future__ import annotations

import dataclasses
from pathlib import Path

from tests.graph.conftest import build_graph_deps
from wolves.agent.tools.think import ThinkArgs, _think
from wolves.agent.tools.todo import TodoWriteArgs, _todo_write
from wolves.agent.tools.web_search import WebSearchArgs, _web_search
from wolves.tools._budget_gate import BudgetGate


async def test_think_and_todo_run_on_an_exhausted_gate(tmp_path: Path):
    gate = BudgetGate(budget=1)
    assert gate.try_reserve()
    deps = dataclasses.replace(build_graph_deps(tmp_path), gate=gate, todos=[])

    refused = await _web_search(WebSearchArgs(query="saka fitness"), deps)
    assert not refused.ok and refused.error is not None and refused.error.type == "budget_exhausted"

    thought = await _think(ThinkArgs(thought="the market move predates the injury news"), deps)
    assert thought.ok

    written = await _todo_write(
        TodoWriteArgs.model_validate({"todos": [{"content": "invert the England gap", "status": "in_progress"}]}),
        deps,
    )
    assert written.ok
    assert [t.content for t in deps.todos] == ["invert the England gap"]
    deps.runtime.shutdown()
