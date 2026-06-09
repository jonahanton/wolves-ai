from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx
import pytest

from wolves.agent_tools.hosts import HostLimits
from wolves.agent_tools.settings import WebFetchSettings
from wolves.clients.fetch._pdf import set_pdf_extractor
from wolves.clients.fetch._ssrf import (
    SSRFBlocked,
    check,
    check_url,
)
from wolves.clients.fetch.fetch import (
    WebFetchArgs,
    make_spec,
)


@dataclass
class StubFetchDeps:
    host_limits: HostLimits = field(default_factory=HostLimits.unlimited)


@pytest.fixture
def fetch_deps() -> StubFetchDeps:
    return StubFetchDeps()


@pytest.fixture(autouse=True)
def _allow_dns(monkeypatch):
    """Bypass real DNS by default; individual tests override as needed."""

    def _ok(host, *_args, **_kwargs):
        return [(2, 1, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        _ok,
    )


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
    return httpx.Response(
        200,
        content=_HTML_PAGE,
        headers={"content-type": "text/html; charset=utf-8"},
    )


async def test_happy_path_returns_markdown(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok
    assert out.payload.title == "Hello World"
    assert "body of the article" in out.payload.content
    assert "Hello World" in out.payload.headings
    assert "Subsection" in out.payload.headings
    assert out.sources and out.sources[0].source_type == "web"


async def test_max_chars_truncation_reports_total(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(
        WebFetchArgs(url="https://example.org/x", max_chars=50),
        fetch_deps,
    )
    assert out.ok
    assert len(out.payload.content) <= 50
    assert out.payload.total_chars > 50
    assert out.payload.truncated is True


async def test_headings_only(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(
        WebFetchArgs(url="https://example.org/x", headings_only=True),
        fetch_deps,
    )
    assert out.ok
    assert out.payload.headings == ["Hello World", "Subsection"]
    assert "Hello World" in out.payload.content
    assert "Subsection" in out.payload.content


async def test_non_html_non_pdf_content_type_rejected(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"binary data",
            headers={"content-type": "application/octet-stream"},
        )

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UnsupportedContentType"


async def test_too_large_via_content_length(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"<html></html>",
            headers={
                "content-type": "text/html",
                "content-length": str(10**9),
            },
        )

    spec = make_spec(
        WebFetchSettings(max_bytes=1024),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooLarge"


async def test_redirect_followed(fetch_deps):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"})
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/start"), fetch_deps)
    assert out.ok
    assert "/final" in out.payload.url


async def test_too_many_redirects(fetch_deps):
    def handler(request):
        return httpx.Response(302, headers={"location": "/loop"})

    spec = make_spec(
        WebFetchSettings(max_redirects=2),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooManyRedirects"


async def test_redirect_to_private_blocked(monkeypatch, fetch_deps):
    def handler(request):
        if "internal" in str(request.url):
            return _ok_html(request)
        return httpx.Response(302, headers={"location": "https://internal.local/x"})

    def _resolver(host, *_args, **_kwargs):
        if host == "internal.local":
            return [(2, 1, 0, "", ("10.0.0.5", 0))]
        return [(2, 1, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        _resolver,
    )
    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


async def test_robots_disallow_when_enabled(fetch_deps):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /\n",
                headers={"content-type": "text/plain"},
            )
        return _ok_html(request)

    spec = make_spec(
        WebFetchSettings(respect_robots=True),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


async def test_robots_default_off_allows_fetch(fetch_deps):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /\n",
                headers={"content-type": "text/plain"},
            )
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok


async def test_host_limit_slot_acquired(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    fetch_deps.host_limits = HostLimits.from_capacities({"web": 1})
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok


def test_ssrf_rejects_non_http_scheme():
    with pytest.raises(SSRFBlocked):
        check_url("file:///etc/passwd")
    with pytest.raises(SSRFBlocked):
        check_url("javascript:alert(1)")


def test_ssrf_rejects_loopback(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("127.0.0.1", 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("http://localhost.example/x")


def test_ssrf_rejects_link_local(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("169.254.169.254", 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("http://imdsv1.example/x")


def test_ssrf_rejects_dns_failure(monkeypatch):
    import socket

    def _raise(*_a, **_kw):
        raise socket.gaierror("nope")

    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        _raise,
    )
    with pytest.raises(SSRFBlocked):
        check("https://no-such-host.example/x")


async def test_blocked_ip_at_input(monkeypatch, fetch_deps):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("127.0.0.1", 0))],
    )
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(WebFetchArgs(url="https://localhost.example/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


def test_extra_args_forbidden():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WebFetchArgs(url="https://x.example", weird=1)


async def test_5xx_returns_upstream_error(fetch_deps):
    def handler(_request):
        return httpx.Response(503, content=b"<html></html>")

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UpstreamError"
    assert "503" in out.error.message


async def test_redirect_with_no_location_is_upstream_error(fetch_deps):
    def handler(_request):
        return httpx.Response(302, content=b"")

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UpstreamError"


async def test_too_large_streamed_body_without_content_length(fetch_deps):
    big = b"<html><body>" + b"x" * 5000 + b"</body></html>"

    def handler(_request):
        return httpx.Response(
            200,
            content=big,
            headers={"content-type": "text/html"},
        )

    spec = make_spec(
        WebFetchSettings(max_bytes=1024),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooLarge"


@pytest.mark.parametrize(
    "private_ip",
    ["127.0.0.1", "169.254.169.254", "10.0.0.5", "192.168.1.1"],
)
async def test_redirect_to_blocked_ip(monkeypatch, fetch_deps, private_ip):
    def handler(request):
        return httpx.Response(302, headers={"location": "https://internal.local/x"})

    def _resolver(host, *_args, **_kwargs):
        if host == "internal.local":
            return [(2, 1, 0, "", (private_ip, 0))]
        return [(2, 1, 0, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        _resolver,
    )
    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


def test_ssrf_rejects_ipv4_mapped_ipv6_loopback(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(10, 1, 0, "", ("::ffff:127.0.0.1", 0, 0, 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://example.com/x")


def test_ssrf_rejects_ipv4_mapped_ipv6_imds(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(10, 1, 0, "", ("::ffff:169.254.169.254", 0, 0, 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://example.com/x")


def test_ssrf_rejects_when_any_a_record_is_private(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [
            (2, 1, 0, "", ("93.184.216.34", 0)),
            (2, 1, 0, "", ("10.0.0.1", 0)),
        ],
    )
    with pytest.raises(SSRFBlocked):
        check("https://round-robin.example/x")


async def test_fetch_timeout_returns_timeout_error(monkeypatch, fetch_deps):
    async def _hang(*_args, **_kwargs):
        await asyncio.sleep(5)
        raise AssertionError("should have timed out")

    spec = make_spec(WebFetchSettings(timeout_seconds=0.05, total_timeout_seconds=0.05, pdf_total_timeout_seconds=0.05))

    monkeypatch.setattr(
        "wolves.clients.fetch.fetch._fetch_with_redirects",
        _hang,
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Timeout"
    assert out.error.retryable is True


async def test_pagination_past_total_returns_empty(fetch_deps):
    spec = make_spec(transport_factory=_transport(_ok_html))
    out = await spec.fn(
        WebFetchArgs(url="https://example.org/x", max_chars=100, start_index=10_000),
        fetch_deps,
    )
    assert out.ok
    assert out.payload.content == ""
    assert out.payload.total_chars > 0
    assert out.payload.truncated is False


async def test_httpx_error_returns_upstream_error(fetch_deps):
    def handler(_request):
        raise httpx.ConnectError("connection refused")

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "UpstreamError"
    assert out.error.retryable is True


def test_ssrf_rejects_url_with_embedded_credentials():
    with pytest.raises(SSRFBlocked):
        check_url("https://user:pass@example.com/x")
    with pytest.raises(SSRFBlocked):
        check_url("https://user@example.com/x")


def test_ssrf_rejects_empty_scheme():
    with pytest.raises(SSRFBlocked):
        check_url("//example.com/x")


def test_ssrf_rejects_missing_host():
    with pytest.raises(SSRFBlocked):
        check_url("https:///path")


async def test_unknown_charset_falls_back_to_utf8(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=_HTML_PAGE,
            headers={"content-type": "text/html; charset=bogus-encoding"},
        )

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok
    assert "body of the article" in out.payload.content


async def test_robots_allow_rule_permits_path(fetch_deps):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private\nAllow: /public\n",
                headers={"content-type": "text/plain"},
            )
        return _ok_html(request)

    spec = make_spec(
        WebFetchSettings(respect_robots=True),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/public/page"), fetch_deps)
    assert out.ok


async def test_robots_fetch_failure_is_permissive(fetch_deps):
    def handler(request):
        if request.url.path == "/robots.txt":
            raise httpx.ConnectError("robots unreachable")
        return _ok_html(request)

    spec = make_spec(
        WebFetchSettings(respect_robots=True),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert out.ok


async def test_https_to_http_redirect_blocked(fetch_deps):
    def handler(request):
        if request.url.scheme == "https":
            return httpx.Response(301, headers={"location": "http://example.org/x"})
        return _ok_html(request)

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "Blocked"


class _StubPDFExtractor:
    def extract_text(self, pdf_bytes: bytes, *, start: int = 1, end: int | None = None) -> tuple[str, str | None]:
        return f"--- Page 1/2 ---\nstub content (bytes={len(pdf_bytes)})", "Stub Title"


@pytest.fixture(autouse=True)
def _stub_pdf_extractor():
    from wolves.clients.fetch._pdf import get_pdf_extractor

    original = get_pdf_extractor()
    set_pdf_extractor(_StubPDFExtractor())
    yield
    set_pdf_extractor(original)


async def test_pdf_content_type_returns_payload(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"%PDF-1.4 fake",
            headers={"content-type": "application/pdf"},
        )

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/doc.pdf"), fetch_deps)
    assert out.ok
    assert out.payload.is_pdf is True
    assert out.payload.title == "Stub Title"
    assert "stub content" in out.payload.content
    assert out.sources and out.sources[0].source_type == "web"


async def test_pdf_url_suffix_detected(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"%PDF-1.4 fake",
            headers={"content-type": "application/octet-stream"},
        )

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/report.pdf"), fetch_deps)
    assert out.ok
    assert out.payload.is_pdf is True


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


async def test_pdf_max_chars_truncation(fetch_deps):
    class _LongExtractor:
        def extract_text(self, pdf_bytes: bytes, *, start: int = 1, end: int | None = None) -> tuple[str, str | None]:
            return "x" * 10_000, None

    set_pdf_extractor(_LongExtractor())

    def handler(_request):
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    spec = make_spec(transport_factory=_transport(handler))
    out = await spec.fn(WebFetchArgs(url="https://example.org/x", max_chars=100), fetch_deps)
    assert out.ok
    assert len(out.payload.content) == 100
    assert out.payload.total_chars == 10_000
    assert out.payload.truncated is True


async def test_pdf_uses_larger_byte_cap_than_html(fetch_deps):
    """A PDF above the HTML cap but under the PDF cap is accepted."""
    big = b"%PDF-1.4" + b"x" * 8000

    def handler(_request):
        return httpx.Response(200, content=big, headers={"content-type": "application/pdf"})

    spec = make_spec(
        WebFetchSettings(max_bytes=1024, pdf_max_bytes=1024 * 1024),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/big.pdf"), fetch_deps)
    assert out.ok
    assert out.payload.is_pdf is True


async def test_pdf_over_pdf_cap_rejected(fetch_deps):
    def handler(_request):
        return httpx.Response(
            200,
            content=b"%PDF-1.4",
            headers={"content-type": "application/pdf", "content-length": str(10**9)},
        )

    spec = make_spec(
        WebFetchSettings(pdf_max_bytes=1024),
        transport_factory=_transport(handler),
    )
    out = await spec.fn(WebFetchArgs(url="https://example.org/huge.pdf"), fetch_deps)
    assert not out.ok
    assert out.error and out.error.type == "TooLarge"


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
    assert received_headers, "redirect to other.example.org was never reached"
    final = received_headers[-1]
    assert "authorization" not in {k.lower() for k in final}
    assert "cookie" not in {k.lower() for k in final}


def test_ssrf_rejects_localhost_hostname(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("127.0.0.1", 0))],
    )
    with pytest.raises(SSRFBlocked, match="local"):
        check("http://localhost/x")


def test_ssrf_rejects_dotlocal_hostname(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("192.168.1.5", 0))],
    )
    with pytest.raises(SSRFBlocked, match="local"):
        check("http://printer.local/x")


@pytest.mark.parametrize(
    "ip",
    [
        "169.254.169.254",  # AWS IMDS
        "100.100.100.200",  # Alibaba metadata
    ],
)
def test_ssrf_rejects_metadata_ips(ip, monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", (ip, 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://metadata.example/x")


def test_ssrf_rejects_cgnat(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(2, 1, 0, "", ("100.64.0.1", 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://cgnat.example/x")


def test_ssrf_rejects_6to4(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(10, 1, 0, "", ("2002:c000:0204::", 0, 0, 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://sixto4.example/x")


def test_ssrf_rejects_ipv6_aws_imds(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        lambda *a, **kw: [(10, 1, 0, "", ("fd00:ec2::254", 0, 0, 0))],
    )
    with pytest.raises(SSRFBlocked):
        check("https://imdsv2.example/x")
