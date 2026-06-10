from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import random
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_MAX_DELAY = 15.0
_DEFAULT_BASE_DELAY = 2.0


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        pass
    else:
        return max(0.0, seconds)

    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None

    now = _dt.datetime.now(tz=target.tzinfo or _dt.UTC)
    delta = (target - now).total_seconds()
    return max(0.0, delta)


def _parse_rate_limit_reset(value: str | None) -> float | None:
    """Parse ``X-RateLimit-Reset``: seconds-until-reset or epoch seconds.

    Magnitudes >= 1e9 are treated as epoch (post-2001), smaller values as
    seconds-until-reset.
    """
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except ValueError:
        return None

    if seconds >= 1_000_000_000:
        now = _dt.datetime.now(tz=_dt.UTC).timestamp()
        return max(0.0, seconds - now)
    return max(0.0, seconds)


def _retry_hint_from_response(
    response: httpx.Response,
) -> tuple[float | None, str]:
    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
    if retry_after is not None:
        return retry_after, " via Retry-After"

    reset = _parse_rate_limit_reset(response.headers.get("X-RateLimit-Reset"))
    if reset is not None:
        return reset, " via X-RateLimit-Reset"

    return None, ""


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    max_delay: float = _DEFAULT_MAX_DELAY,
    log_prefix: str = "HTTP",
    **kwargs: object,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff.

    Retries on 5xx, 429, and transport errors. Honours ``Retry-After``
    and ``X-RateLimit-Reset`` hints, clamped to ``max_delay``.
    """
    last_error: BaseException = RuntimeError("no attempts")

    for attempt in range(max_retries):
        hint: float | None = None
        hint_label = ""
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code < 500 and response.status_code != 429:
                return response
            last_error = httpx.HTTPStatusError(
                str(response.status_code),
                request=response.request,
                response=response,
            )
            hint, hint_label = _retry_hint_from_response(response)
        except httpx.TransportError as exc:
            last_error = exc

        if attempt < max_retries - 1:
            backoff = base_delay * 2**attempt + random.uniform(0, 1)
            delay = min(hint if hint is not None else backoff, max_delay)
            logger.warning(
                "%s retry %d/%d (%.1fs%s): %s",
                log_prefix,
                attempt + 1,
                max_retries,
                delay,
                hint_label,
                url,
            )
            await asyncio.sleep(delay)

    raise last_error
