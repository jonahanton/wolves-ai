from __future__ import annotations

import socket

import pytest

from wolves.clients.fetch._ssrf import SSRFBlocked, check, check_url


def _resolver(*ips: str):
    return lambda *a, **kw: [(10 if ":" in ip else 2, 1, 0, "", (ip, 0)) for ip in ips]


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "169.254.169.254",  # AWS IMDSv1 / Azure / GCP metadata
        "100.100.100.200",  # Alibaba metadata
        "100.64.0.1",  # carrier-grade NAT
        "::ffff:127.0.0.1",  # IPv4-mapped IPv6 loopback
        "::ffff:169.254.169.254",  # IPv4-mapped IPv6 metadata
        "2002:c000:0204::",  # 6to4
        "fd00:ec2::254",  # AWS IMDSv2 IPv6
    ],
)
def test_rejects_hosts_resolving_to_blocked_addresses(ip, monkeypatch):
    monkeypatch.setattr("wolves.clients.fetch._ssrf.socket.getaddrinfo", _resolver(ip))
    with pytest.raises(SSRFBlocked):
        check("https://h.example/x")


def test_rejects_when_any_resolved_record_is_private(monkeypatch):
    monkeypatch.setattr(
        "wolves.clients.fetch._ssrf.socket.getaddrinfo",
        _resolver("93.184.216.34", "10.0.0.1"),
    )
    with pytest.raises(SSRFBlocked):
        check("https://round-robin.example/x")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "//example.com/x",
        "https:///path",
        "https://user:pass@example.com/x",
        "https://user@example.com/x",
    ],
)
def test_rejects_malformed_or_non_http_urls(url):
    with pytest.raises(SSRFBlocked):
        check_url(url)


@pytest.mark.parametrize("host", ["localhost", "printer.local"])
def test_rejects_local_hostnames_before_dns(host, monkeypatch):
    monkeypatch.setattr("wolves.clients.fetch._ssrf.socket.getaddrinfo", _resolver("93.184.216.34"))
    with pytest.raises(SSRFBlocked, match="local"):
        check(f"http://{host}/x")


def test_rejects_on_dns_failure(monkeypatch):
    def _raise(*_a, **_kw):
        raise socket.gaierror("nope")

    monkeypatch.setattr("wolves.clients.fetch._ssrf.socket.getaddrinfo", _raise)
    with pytest.raises(SSRFBlocked):
        check("https://no-such-host.example/x")
