from __future__ import annotations

import hashlib
from datetime import UTC, datetime
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

    def get(self, url: str) -> CachedArticle | None:
        path = self._path(url)
        if not path.exists():
            return None
        try:
            return CachedArticle.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return None

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
