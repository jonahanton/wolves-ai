from __future__ import annotations

from pathlib import Path

from tests.graph.conftest import build_graph_deps, build_run_store
from wolves.config import Settings
from wolves.graph.blackboard import Blackboard
from wolves.graph.contracts import GraphPatch, NodeOutcome, NodePatch
from wolves.graph.master import admit


def _patch(node_id: str, *, kind: str = "research", replaces: str | None = None) -> NodePatch:
    return NodePatch(node_id=node_id, kind=kind, objective=node_id, brief="...", replaces=replaces)


def test_rebrief_lineage_rules(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local")
    board = Blackboard(artifacts=build_run_store(tmp_path), ledger=deps.ledger, runtime=deps.runtime)
    failed = _patch("research-news")
    board.merge([failed], [NodeOutcome(node_id="research-news", kind="research", ok=False, error="boom")])

    first = GraphPatch(ops=[_patch("research-news-2", replaces="research-news")])
    admitted, dropped = admit(first, board=board, settings=settings)
    assert [op.node_id for op in admitted] == ["research-news-2"]
    assert dropped == []
    board.merge(admitted, [NodeOutcome(node_id="research-news-2", kind="research", ok=True)])
    assert board.nodes[0].replaced_by == "research-news-2"

    second = GraphPatch(
        ops=[
            _patch("research-news-3", replaces="research-news"),
            _patch("research-news-4", replaces="research-never-existed"),
        ]
    )
    admitted, dropped = admit(second, board=board, settings=settings)
    assert admitted == []
    assert "already superseded" in dropped[0]
    assert "unknown node" in dropped[1]
    deps.runtime.shutdown()


def test_per_kind_node_budgets(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_critic_nodes=1, graph_max_wave_workers=4)
    board = Blackboard(artifacts=build_run_store(tmp_path), ledger=deps.ledger, runtime=deps.runtime)
    board.merge(
        [_patch("critic-1", kind="critic")],
        [NodeOutcome(node_id="critic-1", kind="critic", ok=True)],
    )

    patch = GraphPatch(ops=[_patch("critic-2", kind="critic"), _patch("research-1")])
    admitted, dropped = admit(patch, board=board, settings=settings)

    assert [op.node_id for op in admitted] == ["research-1"]
    assert "critic node budget" in dropped[0]
    deps.runtime.shutdown()


def test_seeded_coverage_does_not_spend_global_node_cap(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_nodes=1, graph_max_wave_workers=2)
    board = Blackboard(artifacts=build_run_store(tmp_path), ledger=deps.ledger, runtime=deps.runtime)
    coverage = _patch("coverage-research")
    board.merge([coverage], [NodeOutcome(node_id="coverage-research", kind="research", ok=True)], advance_wave=False)

    admitted, dropped = admit(GraphPatch(ops=[_patch("research-1")]), board=board, settings=settings)

    assert [op.node_id for op in admitted] == ["research-1"]
    assert dropped == []
    deps.runtime.shutdown()


def test_unadjudicated_branch_drops_forecast_until_audited(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_wave_workers=2)
    store = build_run_store(tmp_path)
    entry = deps.ledger.append(
        claim="France market is materially higher than the model",
        source_url="internal://get_odds",
        status="confirmed",
        mechanism="market disagreement",
        proposed_delta=0.05,
        team_id="france",
    )
    store.add(
        kind="evidence",
        created_by="research-news",
        summary="france market premium branch",
        payload={
            "summary": "France market premium needs pricing.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "The market may know something about France.",
                    "support": "Current odds sit well above the model.",
                    "collapse_condition": "Collapse if inside the model uncertainty band.",
                    "source_ids": [entry.id],
                    "confidence": "medium",
                    "suggested_quant_question": "Price the market gap.",
                }
            ],
        },
    )
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    forecast = _patch("forecast", kind="forecast")

    first, first_drops = admit(GraphPatch(ops=[forecast]), board=board, settings=settings)
    second, second_drops = admit(GraphPatch(ops=[forecast]), board=board, settings=settings)
    store.add(
        kind="mixture",
        created_by="quant-mixture",
        summary="france branch priced",
        payload={
            "weights": {"model_base": 0.8, "france-market-premium": 0.2},
            "branch_audit": {
                "verdict": "France branch priced.",
                "checks": [
                    {
                        "key": "france-market-premium",
                        "status": "priced",
                        "summary": "France market premium is priced as its own world.",
                    }
                ],
            },
        },
    )
    third, third_drops = admit(GraphPatch(ops=[forecast]), board=board, settings=settings)

    assert first == []
    assert "branch coverage needs one focused follow-up" in first_drops[0]
    assert second == []
    assert "branch coverage needs one focused follow-up" in second_drops[0]
    assert [op.node_id for op in third] == ["forecast"]
    assert third_drops == []
    deps.runtime.shutdown()


def test_superseded_research_branches_do_not_force_follow_up(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    store = build_run_store(tmp_path)
    entry = deps.ledger.append(
        claim="France market is materially higher than the model",
        source_url="internal://get_odds",
        status="confirmed",
        mechanism="market disagreement",
        proposed_delta=0.05,
        team_id="france",
    )
    artifact = store.add(
        kind="evidence",
        created_by="research-news",
        summary="old France branch",
        payload={
            "summary": "Old France branch.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "The market may know something about France.",
                    "support": "Current odds sit well above the model.",
                    "collapse_condition": "Collapse if inside the model uncertainty band.",
                    "source_ids": [entry.id],
                    "confidence": "medium",
                    "suggested_quant_question": "Price the market gap.",
                }
            ],
        },
    )
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)
    old = _patch("research-news")
    board.merge([old], [NodeOutcome(node_id="research-news", kind="research", ok=True, artifact_ids=[artifact.id])])
    replacement = _patch("research-news-2", replaces="research-news")
    board.merge([replacement], [NodeOutcome(node_id="research-news-2", kind="research", ok=True)])

    coverage = board.branch_coverage()

    assert coverage.candidate_keys == []
    assert coverage.needs_follow_up is False
    deps.runtime.shutdown()


def test_branch_audit_allows_two_world_forecast(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_wave_workers=2)
    store = build_run_store(tmp_path)
    entry = deps.ledger.append(
        claim="France market is materially higher than the model",
        source_url="internal://get_odds",
        status="confirmed",
        mechanism="market disagreement",
        team_id="france",
    )
    store.add(
        kind="evidence",
        created_by="research-news",
        summary="france market premium branch",
        payload={
            "summary": "France market premium needs pricing.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "The market may know something about France.",
                    "support": "Current odds sit well above the model.",
                    "collapse_condition": "Collapse if inside the model uncertainty band.",
                    "confidence": "medium",
                    "source_ids": [entry.id],
                    "suggested_quant_question": "Price the market gap.",
                }
            ],
        },
    )
    store.add(
        kind="mixture",
        created_by="quant-mixture",
        summary="two base worlds",
        payload={
            "weights": {"model_base": 0.27, "market_base": 0.73},
            "branch_audit": {
                "verdict": "France premium merged into the market base.",
                "checks": [
                    {
                        "key": "france-market-premium",
                        "status": "merged_into_base",
                        "hypothesis": "The market may know something about France.",
                        "summary": "The premium is represented by the market-base perturbation.",
                    }
                ],
            },
        },
    )
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    admitted, dropped = admit(GraphPatch(ops=[_patch("forecast", kind="forecast")]), board=board, settings=settings)

    assert [op.node_id for op in admitted] == ["forecast"]
    assert dropped == []
    deps.runtime.shutdown()


def test_unknown_branch_audit_status_still_needs_follow_up(tmp_path: Path):
    deps = build_graph_deps(tmp_path)
    settings = Settings(_env_file=None, storage_mode="local", graph_max_wave_workers=2)
    store = build_run_store(tmp_path)
    entry = deps.ledger.append(
        claim="France market is materially higher than the model",
        source_url="internal://get_odds",
        status="confirmed",
        mechanism="market disagreement",
        team_id="france",
    )
    store.add(
        kind="evidence",
        created_by="research-news",
        summary="france market premium branch",
        payload={
            "summary": "France market premium needs pricing.",
            "candidate_branches": [
                {
                    "branch_id": "france-market-premium",
                    "teams": ["france"],
                    "hypothesis": "The market may know something about France.",
                    "support": "Current odds sit well above the model.",
                    "collapse_condition": "Collapse if inside the model uncertainty band.",
                    "confidence": "medium",
                    "source_ids": [entry.id],
                    "suggested_quant_question": "Price the market gap.",
                }
            ],
        },
    )
    store.add(
        kind="mixture",
        created_by="quant-mixture",
        summary="unknown branch audit",
        payload={
            "weights": {"model_base": 0.27, "market_base": 0.73},
            "branch_audit": {
                "verdict": "Unclear.",
                "checks": [{"key": "france-market-premium", "status": "looked_at"}],
            },
        },
    )
    board = Blackboard(artifacts=store, ledger=deps.ledger, runtime=deps.runtime)

    admitted, dropped = admit(GraphPatch(ops=[_patch("forecast", kind="forecast")]), board=board, settings=settings)

    assert admitted == []
    assert "branch coverage needs one focused follow-up" in dropped[0]
    deps.runtime.shutdown()
