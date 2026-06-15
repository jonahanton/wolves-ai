from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time
from pathlib import Path

from pydantic import BaseModel


class CachedArticle(BaseModel):
    url: str
    final_url: str
    title: str | None
    text: str
    retrieved_at: str
    run_id: str

    def age_hours(self, *, now: datetime | None = None) -> float:
        retrieved = datetime.fromisoformat(self.retrieved_at)
        return ((now or datetime.now(UTC)) - retrieved).total_seconds() / 3600


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


class ArticleCache:
    """Cross-run cache of fetched article text, so a page read yesterday is
    reread from disk with its retrieval timestamp instead of refetched."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, url: str) -> Path:
        return self.root / f"{_url_hash(url)}.json"

    def get(self, url: str, *, as_of: str | None = None, current_run_id: str | None = None) -> CachedArticle | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            article = CachedArticle.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return None
        latest = _end_of_day(as_of)
        if (
            latest is not None
            and article.run_id != current_run_id
            and datetime.fromisoformat(article.retrieved_at) > latest
        ):
            return None
        return article

    def recent(
        self,
        *,
        max_age_hours: float,
        limit: int = 12,
        as_of: str | None = None,
        current_run_id: str | None = None,
    ) -> list[CachedArticle]:
        """Newest-first cached articles still inside the freshness window."""
        articles: list[CachedArticle] = []
        seen: set[str] = set()
        latest = _end_of_day(as_of)
        now = _freshness_clock(as_of)
        if not self.root.exists():
            return articles
        for path in self.root.glob("*.json"):
            try:
                article = CachedArticle.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            # put() writes the same article under url and final_url.
            if article.final_url in seen:
                continue
            seen.add(article.final_url)
            if (
                latest is not None
                and article.run_id != current_run_id
                and datetime.fromisoformat(article.retrieved_at) > latest
            ):
                continue
            if article.age_hours(now=now) <= max_age_hours:
                articles.append(article)
        articles.sort(key=lambda a: a.retrieved_at, reverse=True)
        return articles[:limit]

    def put(self, *, url: str, final_url: str, title: str | None, text: str, run_id: str) -> CachedArticle:
        article = CachedArticle(
            url=url,
            final_url=final_url,
            title=title,
            text=text,
            retrieved_at=datetime.now(UTC).isoformat(timespec="seconds"),
            run_id=run_id,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        body = article.model_dump_json(indent=1)
        self._path(url).write_text(body, encoding="utf-8")
        if final_url != url:
            self._path(final_url).write_text(body, encoding="utf-8")
        return article


def _end_of_day(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(date.fromisoformat(value), time.max, tzinfo=UTC)
    except ValueError:
        return None


def _freshness_clock(as_of: str | None) -> datetime:
    now = datetime.now(UTC)
    latest = _end_of_day(as_of)
    return min(latest, now) if latest is not None else now
