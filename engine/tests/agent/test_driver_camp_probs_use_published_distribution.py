from __future__ import annotations

from types import SimpleNamespace

from wolves.run_agent import _driver_stats_from_distributions


def test_driver_camp_probs_use_published_distribution_components():
    sidecar = SimpleNamespace(
        teams={
            "england": {
                "champion": SimpleNamespace(
                    components={
                        "model_base": {"weight": 0.2, "mean": 0.06, "sd": 0.01},
                        "market_base": {"weight": 0.5, "mean": 0.08, "sd": 0.01},
                        "market_yamal": {"weight": 0.3, "mean": 0.09, "sd": 0.01},
                    }
                )
            }
        }
    )

    camp_probs, means = _driver_stats_from_distributions(
        sidecar, {"model_base": "model", "market_base": "market", "market_yamal": "market"}
    )

    assert camp_probs["england"] == {"model": 0.06, "market": 0.08375}
    assert means["england"] == [0.06, 0.08, 0.09]
