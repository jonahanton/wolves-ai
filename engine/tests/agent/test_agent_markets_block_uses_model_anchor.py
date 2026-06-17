from __future__ import annotations

from types import SimpleNamespace

from wolves.run_agent import _markets_block


def test_agent_markets_block_uses_supplied_model_anchor() -> None:
    deps = SimpleNamespace(forecaster=SimpleNamespace(champion=SimpleNamespace(blend_weight=0.25)))

    block = _markets_block(
        deps,
        {"england": 0.1, "france": 0.2},
        {"england": 0.3, "france": 0.1},
    )

    assert block is not None
    assert block.model_probs == {"england": 0.1, "france": 0.2}
    assert block.market_probs == {"england": 0.3, "france": 0.1}
