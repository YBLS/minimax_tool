"""Security helpers shared by middleware, persistence and outbound HTTP."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import anyio

_SENSITIVE_KEYS = {
    "authorization", "api_key", "apikey", "api-key", "x-api-key",
    "proxy-authorization", "cookie", "set-cookie", "password", "secret", "token",
}

# Docker Desktop / corporate transparent proxies commonly synthesize addresses
# from RFC 2544's benchmarking block for public hostnames. It is non-routable on
# the public Internet but is not an internal service range; permit it while
# continuing to reject RFC1918, loopback, link-local and metadata targets.
_PROXY_BENCHMARK_NET = ipaddress.ip_network("198.18.0.0/15")


def redact_sensitive(value: Any) -> Any:
    """Return a JSON-compatible copy with credentials recursively removed."""
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in _SENSITIVE_KEYS else redact_sensitive(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str) and value.lower().startswith(("bearer ", "basic ")):
        return "[REDACTED]"
    return value


async def validate_outbound_url(url: str, *, allow_private: bool = False) -> None:
    """Reject non-HTTP and private/link-local targets to reduce SSRF exposure."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Outbound URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in outbound URLs are not allowed")
    if allow_private:
        return

    def resolve() -> set[str]:
        return {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}

    try:
        addresses = await anyio.to_thread.run_sync(resolve)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve outbound host: {parsed.hostname}") from exc
    for raw in addresses:
        ip = ipaddress.ip_address(raw.split("%")[0])
        if ip in _PROXY_BENCHMARK_NET:
            continue
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or
            ip.is_multicast or ip.is_reserved or ip.is_unspecified
        ):
            raise ValueError(f"Outbound host resolves to a non-public address: {parsed.hostname}")
