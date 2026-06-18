from __future__ import annotations

from wolves.clients.api_football.client import _goal_events


def _item(events: list[dict]) -> dict:
    return {"teams": {"home": {"id": 10}, "away": {"id": 20}}, "events": events}


def test_goal_events_order_credit_and_exclusions():
    goals = _goal_events(
        _item(
            [
                {"type": "Goal", "detail": "Normal Goal", "team": {"id": 20}, "time": {"elapsed": 51}},
                {"type": "Goal", "detail": "Own Goal", "team": {"id": 20}, "time": {"elapsed": 23}},
                {"type": "Goal", "detail": "Missed Penalty", "team": {"id": 10}, "time": {"elapsed": 40}},
                {
                    "type": "Goal",
                    "detail": "Penalty",
                    "team": {"id": 10},
                    "time": {"elapsed": 120},
                    "comments": "Penalty Shootout",
                },
                {"type": "Card", "detail": "Red Card", "team": {"id": 10}, "time": {"elapsed": 70}},
            ]
        )
    )
    assert [(g.minute, g.side) for g in goals] == [(23, "home"), (51, "away")]


def test_goal_without_elapsed_minute_is_dropped():
    goals = _goal_events(_item([{"type": "Goal", "detail": "Normal Goal", "team": {"id": 10}, "time": {}}]))
    assert goals == []
