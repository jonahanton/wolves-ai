from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
_ISO_DATE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b")
_MONTH_DAY = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\.?\s+([0-3]?\d)(?:,\s*(20\d{2}))?\b",
    re.IGNORECASE,
)
_DAY_MONTH = re.compile(
    r"\b([0-3]?\d)\s+("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\.?(?:\s+(20\d{2}))?\b",
    re.IGNORECASE,
)


def _coerce_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _as_date(as_of: str | date) -> date:
    if isinstance(as_of, date):
        return as_of
    return date.fromisoformat(as_of)


def future_date_mentions(text: str, *, as_of: str | date) -> list[str]:
    """Return explicit date mentions after the run as-of date."""
    today = _as_date(as_of)
    found: list[str] = []
    seen: set[tuple[date, str]] = set()

    def add(raw: str, when: date | None) -> None:
        if when is None or when <= today:
            return
        key = (when, raw)
        if key in seen:
            return
        seen.add(key)
        found.append(raw)

    for match in _ISO_DATE.finditer(text):
        add(match.group(0), _coerce_date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
    for match in _MONTH_DAY.finditer(text):
        month = _MONTHS[match.group(1).rstrip(".").lower()]
        year = int(match.group(3)) if match.group(3) else today.year
        add(match.group(0), _coerce_date(year, month, int(match.group(2))))
    for match in _DAY_MONTH.finditer(text):
        month = _MONTHS[match.group(2).rstrip(".").lower()]
        year = int(match.group(3)) if match.group(3) else today.year
        add(match.group(0), _coerce_date(year, month, int(match.group(1))))
    return found
