from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx
import pytest

from wolves.agent_tools.hosts import HostLimits
from wolves.agent_tools.settings import WebFetchSettings
from wolves.clients.fetch._pdf import get_pdf_extractor, set_pdf_extractor
from wolves.clients.fetch.fetch import WebFetchArgs, make_spec


@dataclass
class StubFetchDeps:
    host_limits: HostLimits = field(default_factory=HostLimits.unlimited)


@pytest.fixture
def fetch_deps() -> StubFetchDeps:
    return StubFetchDeps()


@pytest.fixture(autouse=True)
def _allow_dns(monkeypatch):
    """Bypass real DNS by default; individual tests override as needed."""
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("93.184.216.34", 0))],
    )


class _StubPDFExtractor:
    def extract_text(self, pdf_bytes: bytes, *, start: int = 1, end: int | None = None) -> tuple[str, str | None]:
        return f"stub content (bytes={len(pdf_bytes)})", "Stub Title"


@pytest.fixture(autouse=True)
def _stub_pdf_extractor():
    original = get_pdf_extractor()
    set_pdf_extractor(_StubPDFExtractor())
    yield
    set_pdf_extractor(original)


def _transport(handler):
    return lambda: httpx.MockTransport(handler)


_HTML_PAGE = b"""
<html><head><title>Hello World</title></head>
<body>
<h1>Hello World</h1>
<p>This is the body of the article. It contains useful information that
should be extracted by trafilatura. The minimum length means we need to
write a full sentence here so the extractor takes it seriously.</p>
<h2>Subsection</h2>
<p>More content follows under the subsection. Paragraph two of the article
sits below this heading and rounds out the body.</p>
</body></html>
"""


def _ok_html(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_HTML_PAGE, headers={"content-type": "text/html; charset=utf-8"})


async def test_happy_path_returns_markdown_with_headings_and_source(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok
    assert out.payload.title == "Hello World"
    assert "body of the article" in out.payload.content
    assert out.payload.headings == ["Hello World", "Subsection"]
    assert out.sources and out.sources[0].source_type == "web"


async def test_max_chars_truncation_reports_total(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x", max_chars=50), fetch_deps)
    assert out.ok
    assert len(out.payload.content) <= 50
    assert out.payload.total_chars > 50
    assert out.payload.truncated is True


async def test_pagination_past_total_returns_empty_not_truncated(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x", max_chars=100, start_index=10_000), fetch_deps)
    assert out.ok
    assert out.payload.content == ""
    assert out.payload.truncated is False


async def test_headings_only_surveys_structure(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x", headings_only=True), fetch_deps)
    assert out.ok
    assert out.payload.headings == ["Hello World", "Subsection"]


async def test_non_html_non_pdf_content_type_rejected(fetch_deps):
    def handler(_request):
        return httpx.Response(200, content=b"binary", headers={"content-type": "application/octet-stream"})

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UnsupportedContentType"


async def test_declared_content_length_over_cap_rejected(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"<html></html>",
            headers={"content-type": "text/html", "content-length": str(10**9)},
        )

    spec = make_spec(WebFetchSettings(max_bytes=1024), transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooLarge"


async def test_streamed_body_over_cap_rejected_without_content_length(fetch_deps):
    big = b"<html><body>" + b"x" * 5000 + b"</body></html>"

    def handler(_request):
        return httpx.Response(200, content=big, headers={"content-type": "text/html"})

    spec = make_spec(WebFetchSettings(max_bytes=1024), transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooLarge"


async def test_redirect_followed_to_final_url(fetch_deps):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"})
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/start"), fetch_deps)
    assert out.ok
    assert "/final" in out.payload.url


async def test_redirect_loop_rejected(fetch_deps):
    def handler(_request):
        return httpx.Response(302, headers={"location": "/loop"})

    spec = make_spec(WebFetchSettings(max_redirects=2), transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooManyRedirects"


async def test_redirect_to_private_address_blocked(monkeypatch, fetch_deps):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://internal.example/x"})

    def _resolver(host, *_args, **_kwargs):
        ip = "10.0.0.5" if host == "internal.example" else "93.184.216.34"
        return [(2, 1, 0, "", (ip, 0))]

    monkeypatch.setattr("wolves.clients.fetch._ssrf.socket.getaddrinfo", _resolver)
    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


async def test_https_to_http_redirect_downgrade_blocked(fetch_deps):
    def handler(request):
        if request.url.scheme == "https":
            return httpx.Response(301, headers={"location": "http://example.org/x"})
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


async def test_cross_host_redirect_strips_sensitive_headers(fetch_deps):
    received_headers: list[dict] = []

    def handler(request):
        if "original" in str(request.url):
            return httpx.Response(302, headers={"location": "https://other.example.org/x"})
        received_headers.append(dict(request.headers))
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://original.example.org/x"), fetch_deps)
    assert out.ok
    assert received_headers
    final = {k.lower() for k in received_headers[-1]}
    assert "authorization" not in final
    assert "cookie" not in final


async def test_robots_disallow_honoured_when_enabled(fetch_deps):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n", headers={"content-type": "text/plain"})
        return _ok_html(request)

    spec = make_spec(WebFetchSettings(respect_robots=True), transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


async def test_upstream_5xx_returns_upstream_error(fetch_deps):
    def handler(_request):
        return httpx.Response(503, content=b"<html></html>")

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UpstreamError"
    assert "503" in out.error.message


async def test_timeout_returns_retryable_timeout_error(monkeypatch, fetch_deps):
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr("wolves.clients.fetch.fetch._fetch_with_redirects", _hang)
    spec = make_spec(WebFetchSettings(total_timeout_seconds=0.05, pdf_total_timeout_seconds=0.05))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Timeout"
    assert out.error.retryable is True


async def test_unknown_charset_falls_back_to_utf8(fetch_deps):
    def handler(_request):
        return httpx.Response(200, content=_HTML_PAGE, headers={"content-type": "text/html; charset=bogus"})

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok
    assert "body of the article" in out.payload.content


@pytest.mark.parametrize(
    ("content_type", "url"),
    [
        ("application/pdf", "https://example.org/doc"),
        ("application/octet-stream", "https://example.org/report.pdf"),
    ],
)
async def test_pdf_detected_by_content_type_or_suffix(content_type, url, fetch_deps):
    def handler(_request):
        return httpx.Response(200, content=b"%PDF-1.4 fake", headers={"content-type": content_type})

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url=url), fetch_deps)
    assert out.ok
    assert out.payload.is_pdf is True
    assert "stub content" in out.payload.content


async def test_pdf_page_range_passed_to_extractor(fetch_deps):
    calls: list[dict] = []

    class _RecordingExtractor:
        def extract_text(self, pdf_bytes: bytes, *, start: int = 1, end: int | None = None) -> tuple[str, str | None]:
            calls.append({"start": start, "end": end})
            return "page content", None

    set_pdf_extractor(_RecordingExtractor())

    def handler(_request):
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    spec = make_spec(transport_factory=_transport(handler))
    await spec.fn(WebFetchArgs(url="https://example.org/x", start_page=3, end_page=7), fetch_deps)
    assert calls == [{"start": 3, "end": 7}]


async def test_pdf_byte_cap_is_independent_of_html_cap(fetch_deps):
    big = b"%PDF-1.4" + b"x" * 8000

    def handler(_request):
        return httpx.Response(200, content=big, headers={"content-type": "application/pdf"})

    spec = make_spec(WebFetchSettings(max_bytes=1024, pdf_max_bytes=1024 * 1024), transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/big.pdf"), fetch_deps)
    assert out.ok
    assert out.payload.is_pdf is True
