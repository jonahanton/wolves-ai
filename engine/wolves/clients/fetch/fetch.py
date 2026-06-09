from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from pydantic import BaseModel, ConfigDict, Field

from wolves.agent_tools.core import ToolSpec
from wolves.agent_tools.deps import WebFetchDeps
from wolves.agent_tools.errors import ToolTimeoutError
from wolves.agent_tools.hosts import WEB
from wolves.agent_tools.result import (
    SourceRef,
    ToolError,
    ToolResult,
)
from wolves.agent_tools.settings import WebFetchSettings
from wolves.clients.fetch._pdf import get_pdf_extractor
from wolves.clients.fetch._ssrf import (
    SSRFBlocked,
    check,
)

logger = logging.getLogger(__name__)

_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_PDF_CONTENT_TYPE = "application/pdf"
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization", "x-api-key"})


class WebFetchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(description="HTTP(S) URL to fetch.")
    max_chars: int = Field(
        default=5_000,
        ge=1,
        le=50_000,
        description=("Cap on returned markdown characters. Use ``start_index`` to page through longer documents."),
    )
    start_index: int = Field(
        default=0,
        ge=0,
        description="Character offset into the extracted markdown.",
    )
    headings_only: bool = Field(
        default=False,
        description=(
            "Return only the document headings rather than full body. "
            "Useful for surveying long pages before paging through."
        ),
    )
    start_page: int | None = Field(
        default=None,
        ge=1,
        description="First PDF page to extract (1-indexed, inclusive). PDF only.",
    )
    end_page: int | None = Field(
        default=None,
        ge=1,
        description="Last PDF page to extract (1-indexed, inclusive). PDF only.",
    )


class WebFetchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    title: str | None = None
    content: str
    total_chars: int
    truncated: bool = False
    headings: list[str] = Field(default_factory=list)
    is_pdf: bool = False


_DEFAULT_DESCRIPTION = (
    "Fetch a URL and return its main text as markdown. Pair with "
    "``web_search`` once a relevant URL is found and the snippet "
    "alone is not enough. Returns extracted body text, not raw HTML; "
    "use ``max_chars`` + ``start_index`` to page through long pages, "
    "or ``headings_only=True`` to survey structure first. "
    "Also handles PDF URLs: use ``start_page``/``end_page`` to limit "
    "extraction to a page range. "
    "Will not fetch private network addresses or interactive data portals "
    "(download those manually)."
)


TransportFactory = Callable[[], httpx.AsyncBaseTransport]


def make_spec(
    settings: WebFetchSettings | None = None,
    *,
    name: str = "web_fetch",
    description: str = _DEFAULT_DESCRIPTION,
    transport_factory: TransportFactory | None = None,
) -> ToolSpec[WebFetchArgs, WebFetchPayload]:
    s = settings or WebFetchSettings()
    robots_cache: dict[str, RobotFileParser | None] = {}

    async def _run(args: WebFetchArgs, deps: WebFetchDeps) -> ToolResult[WebFetchPayload]:
        try:
            check(args.url)
        except SSRFBlocked as exc:
            return _error(args.url, "Blocked", str(exc))

        async def _fetch_and_extract() -> WebFetchPayload:
            response = await _fetch_with_redirects(args.url, s, robots_cache, transport_factory)
            return await asyncio.to_thread(
                _extract_payload,
                response.url_str,
                response.body,
                response.is_pdf,
                args.max_chars,
                args.start_index,
                args.headings_only,
                args.start_page,
                args.end_page,
            )

        try:
            async with deps.host_limits.slot(WEB):
                # PDF type isn't known until download starts; use the longer fence.
                fence = max(s.total_timeout_seconds, s.pdf_total_timeout_seconds)
                payload = await asyncio.wait_for(
                    _fetch_and_extract(),
                    timeout=fence,
                )
        except _FetchError as exc:
            return _error(args.url, exc.kind, exc.message)
        except (TimeoutError, ToolTimeoutError):
            fence = max(s.total_timeout_seconds, s.pdf_total_timeout_seconds)
            return _error(
                args.url,
                "Timeout",
                f"Fetch timed out after {fence:.0f}s.",
                retryable=True,
            )
        except httpx.HTTPError as exc:
            return _error(
                args.url,
                "UpstreamError",
                f"Fetch failed: {exc}",
                retryable=True,
            )
        sources = [
            SourceRef(
                url=payload.url,
                title=payload.title or payload.url,
                source_type="web",
                snippet=payload.content[:200],
            ),
        ]
        return ToolResult(payload=payload, sources=sources)

    return ToolSpec(
        name=name,
        description=description,
        args_model=WebFetchArgs,
        fn=_run,
    )


class _FetchError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class _FetchResponse:
    def __init__(self, url_str: str, body: bytes | str, *, is_pdf: bool = False) -> None:
        self.url_str = url_str
        self.body = body
        self.is_pdf = is_pdf


async def _fetch_with_redirects(
    url: str,
    settings: WebFetchSettings,
    robots_cache: dict[str, RobotFileParser | None],
    transport_factory: TransportFactory | None,
) -> _FetchResponse:
    headers: dict[str, str] = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/pdf,*/*",
    }
    transport = transport_factory() if transport_factory is not None else None
    initial_scheme = urlparse(url).scheme.lower()
    original_host = urlparse(url).hostname or ""
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=settings.timeout_seconds,
        headers=headers,
        transport=transport,
    ) as client:
        current = url
        for _ in range(settings.max_redirects + 1):
            if settings.respect_robots and not await _allowed_by_robots(
                client, current, settings.user_agent, robots_cache
            ):
                raise _FetchError("Blocked", f"robots.txt disallows {current}")

            async with client.stream("GET", current, headers=headers) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise _FetchError(
                            "UpstreamError",
                            "redirect with no Location header",
                        )
                    next_url = urljoin(current, location)
                    if initial_scheme == "https" and urlparse(next_url).scheme.lower() == "http":
                        raise _FetchError("Blocked", "refusing HTTPS to HTTP redirect downgrade")
                    try:
                        check(next_url)
                    except SSRFBlocked as exc:
                        raise _FetchError("Blocked", str(exc)) from exc
                    # Strip sensitive headers when crossing to a different host.
                    redirect_host = urlparse(next_url).hostname or ""
                    if redirect_host != original_host:
                        headers = {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}
                    current = next_url
                    continue

                if response.status_code >= 400:
                    raise _FetchError(
                        "UpstreamError",
                        f"HTTP {response.status_code} fetching {current}",
                    )

                content_type = response.headers.get("content-type", "")
                is_pdf = _is_pdf(content_type, current)

                if not is_pdf and not _is_html(content_type):
                    raise _FetchError(
                        "UnsupportedContentType",
                        (f"refusing non-HTML/PDF content-type: {content_type or 'unknown'}"),
                    )

                cap = settings.pdf_max_bytes if is_pdf else settings.max_bytes
                declared = _parse_content_length(response.headers.get("content-length"))
                if declared is not None and declared > cap:
                    raise _FetchError(
                        "TooLarge",
                        f"declared content-length {declared} exceeds cap {cap}",
                    )

                raw = await _read_capped(response, cap)
                if is_pdf:
                    return _FetchResponse(str(response.url), raw, is_pdf=True)
                text = _decode(raw, content_type)
                return _FetchResponse(str(response.url), text, is_pdf=False)

        raise _FetchError(
            "TooManyRedirects",
            f"exceeded {settings.max_redirects} redirects from {url}",
        )


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    """Read the streamed response body, raising if it exceeds ``max_bytes``."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise _FetchError(
                "TooLarge",
                f"response body exceeds cap {max_bytes}",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _is_html(content_type: str) -> bool:
    head = content_type.split(";", 1)[0].strip().lower()
    return any(head == ct for ct in _HTML_CONTENT_TYPES)


def _is_pdf(content_type: str, url: str) -> bool:
    head = content_type.split(";", 1)[0].strip().lower()
    return head == _PDF_CONTENT_TYPE or urlparse(url).path.lower().endswith(".pdf")


def _decode(body: bytes, content_type: str | None) -> str:
    charset = "utf-8"
    if content_type and "charset=" in content_type:
        charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


async def _allowed_by_robots(
    client: httpx.AsyncClient,
    url: str,
    user_agent: str,
    cache: dict[str, RobotFileParser | None],
) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        cache[origin] = await _load_robots(client, origin)
    parser = cache[origin]
    if parser is None:
        return True
    return parser.can_fetch(user_agent, url)


async def _load_robots(client: httpx.AsyncClient, origin: str) -> RobotFileParser | None:
    try:
        response = await client.get(f"{origin}/robots.txt")
    except httpx.HTTPError as exc:
        logger.debug("robots.txt fetch failed for %s: %s", origin, exc)
        return None
    if response.status_code >= 400:
        return None
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def _extract_payload(
    url: str,
    body: bytes | str,
    is_pdf: bool,
    max_chars: int,
    start_index: int,
    headings_only: bool,
    start_page: int | None,
    end_page: int | None,
) -> WebFetchPayload:
    if is_pdf:
        if not isinstance(body, bytes):
            raise TypeError(f"PDF body must be bytes, got {type(body).__name__}")
        return _extract_pdf_payload(url, body, max_chars, start_index, start_page, end_page)
    if not isinstance(body, str):
        raise TypeError(f"HTML body must be str, got {type(body).__name__}")
    return _extract_html_payload(url, body, max_chars, start_index, headings_only)


def _extract_pdf_payload(
    url: str,
    pdf_bytes: bytes,
    max_chars: int,
    start_index: int,
    start_page: int | None,
    end_page: int | None,
) -> WebFetchPayload:
    text, title = get_pdf_extractor().extract_text(
        pdf_bytes,
        start=start_page if start_page is not None else 1,
        end=end_page,
    )
    total = len(text)
    sliced = text[start_index : start_index + max_chars]
    truncated = (start_index + max_chars) < total
    return WebFetchPayload(
        url=url,
        title=title,
        content=sliced,
        total_chars=total,
        truncated=truncated,
        is_pdf=True,
    )


def _extract_html_payload(
    url: str,
    html: str,
    max_chars: int,
    start_index: int,
    headings_only: bool,
) -> WebFetchPayload:
    import trafilatura

    body = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        with_metadata=False,
    ) or _plain_text_fallback(html)
    body = body or ""
    title = _safe_title(html, url)
    headings = _extract_headings_from_html(html)

    if headings_only:
        joined = "\n".join(f"- {h}" for h in headings)
        return WebFetchPayload(
            url=url,
            title=title,
            content=joined,
            total_chars=len(joined),
            truncated=False,
            headings=headings,
        )

    total = len(body)
    sliced = body[start_index : start_index + max_chars]
    truncated = (start_index + max_chars) < total
    return WebFetchPayload(
        url=url,
        title=title,
        content=sliced,
        total_chars=total,
        truncated=truncated,
        headings=headings,
    )


def _safe_title(html: str, url: str) -> str | None:
    try:
        from trafilatura.metadata import extract_metadata
    except ImportError:
        return None
    try:
        meta = extract_metadata(html, default_url=url)
    except Exception:
        return None
    if meta is None:
        return None
    title = getattr(meta, "title", None)
    return title if isinstance(title, str) and title else None


def _plain_text_fallback(html: str) -> str:
    try:
        from lxml import html as lxml_html

        tree = lxml_html.fromstring(html)
        for tag in tree.xpath("//script | //style"):
            tag.getparent().remove(tag)
        text = tree.text_content()
    except Exception:
        return ""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _extract_headings_from_html(html: str) -> list[str]:
    try:
        from lxml import html as lxml_html
    except ImportError:
        return []
    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return []
    headings: list[str] = []
    for element in tree.iter("h1", "h2", "h3", "h4", "h5", "h6"):
        text = (element.text_content() or "").strip()
        if text:
            headings.append(text)
    return headings


def _error(
    url: str,
    error_type: str,
    message: str,
    *,
    retryable: bool = False,
) -> ToolResult[WebFetchPayload]:
    return ToolResult(
        ok=False,
        payload=WebFetchPayload(url=url, content="", total_chars=0),
        error=ToolError(type=error_type, message=message, retryable=retryable),
    )
