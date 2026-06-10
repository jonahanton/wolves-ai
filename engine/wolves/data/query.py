"""Typed, read-only query surface over a built dataset: named helpers for the
common questions plus raw SQL passthrough. The connection is read-only, so
arbitrary SQL cannot mutate the dataset."""

from __future__ import annotations

from datetime import date
from types import TracebackType
from typing import Any

import duckdb

from wolves.models.contracts import DatasetHandle


class DatasetQuery:
    def __init__(self, dataset: DatasetHandle) -> None:
        self.dataset = dataset
        self._connection = duckdb.connect(str(dataset.path), read_only=True)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> DatasetQuery:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()

    def sql(self, query: str, parameters: list[Any] | None = None) -> list[dict[str, Any]]:
        """Raw read-only SQL; returns rows as dicts."""
        cursor = self._connection.execute(query, parameters or [])
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def team_form(self, team: str, *, last: int = 10) -> list[dict[str, Any]]:
        return self.sql(
            "select date, home_team, away_team, home_goals, away_goals, tournament, importance, neutral"
            " from matches where home_team = ? or away_team = ? order by date desc limit ?",
            [team, team, last],
        )

    def head_to_head(self, team_a: str, team_b: str, *, since: date | None = None) -> list[dict[str, Any]]:
        return self.sql(
            "select date, home_team, away_team, home_goals, away_goals, tournament from matches"
            " where ((home_team = ? and away_team = ?) or (home_team = ? and away_team = ?)) and date >= ?"
            " order by date desc",
            [team_a, team_b, team_b, team_a, (since or date.min).isoformat()],
        )

    def scoring_rates(self, team: str, *, since: date) -> dict[str, float]:
        rows = self.sql(
            "select avg(case when home_team = ? then home_goals else away_goals end) as scored,"
            " avg(case when home_team = ? then away_goals else home_goals end) as conceded,"
            " count(*) as n from matches where (home_team = ? or away_team = ?) and date >= ?",
            [team, team, team, team, since.isoformat()],
        )
        return rows[0]

    def market_history(self, team: str) -> list[dict[str, Any]]:
        """Closing 1X2 prices for the team across archived tournaments."""
        return self.sql(
            "select tournament, commence_at, home_team, away_team, bookmaker, home_price, draw_price, away_price"
            " from market_closes where home_team = ? or away_team = ? order by commence_at",
            [team, team],
        )

    def covariates(self, team: str) -> dict[str, Any]:
        rows = self.sql("select * from teams where team = ?", [team])
        return rows[0] if rows else {}
