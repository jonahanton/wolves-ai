from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFBlocked(Exception):
    pass


_BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "data", "javascript"})

_METADATA_IPS: frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address] = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS IMDSv1 / Azure / GCP
        ipaddress.ip_address("fd00:ec2::254"),  # AWS IMDSv2 IPv6
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud metadata
    }
)

_BLOCKED_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("2002::/16"),  # 6to4 (RFC 3056)
)

_BLOCKED_HOSTNAMES = frozenset({"localhost", "localhost.localdomain"})


def check_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise SSRFBlocked(
            f"refusing non-http(s) scheme: {scheme!r}" if scheme in _BLOCKED_SCHEMES or scheme else "URL has no scheme"
        )
    if parsed.username or parsed.password:
        raise SSRFBlocked("refusing URL with embedded credentials")
    host = parsed.hostname
    if not host:
        raise SSRFBlocked("URL has no host")
    return host


def check_host(host: str) -> None:
    normalised = host.strip().rstrip(".").lower()
    if normalised in _BLOCKED_HOSTNAMES or normalised.endswith(".local"):
        raise SSRFBlocked(f"refusing local hostname {host!r}")

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SSRFBlocked(f"DNS resolution failed for {host!r}: {exc}") from exc

    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        addr: ipaddress.IPv4Address | ipaddress.IPv6Address = (
            ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
        )
        if (
            addr in _METADATA_IPS
            or any(addr.version == net.version and addr in net for net in _BLOCKED_NETWORKS)
            or addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_unspecified
            or addr.is_reserved
        ):
            raise SSRFBlocked(f"{host!r} resolves to non-public address {ip_str}")


def check(url: str) -> str:
    host = check_url(url)
    check_host(host)
    return host
