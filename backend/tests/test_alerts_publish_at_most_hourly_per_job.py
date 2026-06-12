from __future__ import annotations

from typing import Any

from wolves_backend.clients.alerts import Alerts


class FakeSnsClient:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    def publish(self, **kwargs: Any) -> None:
        self.published.append(kwargs)


def test_repeat_failures_alert_once_and_jobs_do_not_share_the_limit():
    sns = FakeSnsClient()
    alerts = Alerts(topic_arn="arn:aws:sns:eu-west-2:000000000000:wolves-alerts", region="eu-west-2", client=sns)

    alerts.publish("live", "boom")
    alerts.publish("live", "boom again")
    alerts.publish("odds-archive", "different job")

    assert [p["Subject"] for p in sns.published] == [
        "wolves backend job failed: live",
        "wolves backend job failed: odds-archive",
    ]


def test_no_topic_means_log_only():
    alerts = Alerts(topic_arn="", region="eu-west-2")
    alerts.publish("live", "boom")
