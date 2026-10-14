"""
SSRF-safe HTTP fetcher.

Every outbound fetch of a user-supplied URL goes through `safe_fetch`:

* DNS is resolved asynchronously (`loop.getaddrinfo`) and **every** returned
  address must be public. Private, loopback, link-local, reserved, multicast,
  unspecified, CGNAT (100.64/10), 0.0.0.0/8 and IPv4 addresses embedded in
  IPv6 (mapped, NAT64, 6to4, Teredo) are rejected.
* The connection is **pinned** to the checked IP: the request goes to the IP
  literal while the `Host` header and TLS SNI / certificate verification keep
  using the original hostname. A second DNS lookup by the HTTP stack (DNS
  rebinding / TOCTOU) therefore cannot redirect the connection.
* Redirects are followed manually (`settings.fetch_max_redirects`), each hop
  is re-validated and re-pinned; only http/https, no credentials in URLs.
* The body is streamed and capped at `max_bytes` *after* decompression
  (gzip/deflate are decoded here with bounded output — no zip bombs).
* Only allow-listed content types are accepted.

`settings.allow_private_urls` (env ALLOW_PRIVATE_URLS) disables the address
check for development / LAN use; pinning and all other limits stay active.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import zlib
from dataclasses import dataclass, field

import httpx

from app.config import settings

DEFAULT_ACCEPTED_TYPES: frozenset[str] = frozenset(
    {"text/html", "application/xhtml+xml", "text/plain"}
)
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# Networks that are not covered (reliably, across Python versions) by the
# ipaddress `is_*` properties.
_EXTRA_BLOCKED_V4 = (
    ipaddress.ip_network("0.0.0.0/8"),  # "this network"
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT / Tailscale
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
    ipaddress.ip_network("240.0.0.0/4"),  # reserved, incl. broadcast
)
_NAT64_V6 = ipaddress.ip_network("64:ff9b::/96")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FetchError(ValueError):
    """Base class for all fetcher errors (the URL could not be fetched safely)."""


class PrivateAddressError(FetchError):
    """URL resolves to a private/loopback/otherwise non-public address (SSRF guard)."""


class InvalidURLError(FetchError):
    """URL is malformed, uses a forbidden scheme or embeds credentials."""


class TooManyRedirectsError(FetchError):
    """More redirects than `settings.fetch_max_redirects`."""


class ResponseTooLargeError(FetchError):
    """Decoded body exceeds the configured byte limit."""


class UnsupportedContentTypeError(FetchError):
    """Response content type is not in the allow-list."""


class FetchStatusError(FetchError):
    """Final response has a non-success HTTP status."""

    def __init__(self, status: int, url: str):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    status: int
    final_url: str
    headers: httpx.Headers
    body: bytes
    content_type: str | None = None
    charset: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    redirects: list[str] = field(default_factory=list)

    @property
    def not_modified(self) -> bool:
        return self.status == 304

    @property
    def text(self) -> str:
        encoding = self.charset or "utf-8"
        try:
            return self.body.decode(encoding, errors="replace")
        except LookupError:  # unknown charset label from the server
            return self.body.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Address checks
# ---------------------------------------------------------------------------


def is_blocked_ip(ip: IPAddress) -> bool:
    """True if `ip` must not be contacted (anything that is not plain public unicast)."""
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4 tunnelled/embedded in IPv6 is judged by the embedded address.
        if ip.ipv4_mapped is not None:
            return is_blocked_ip(ip.ipv4_mapped)
        if ip in _NAT64_V6:
            return is_blocked_ip(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        if ip.sixtofour is not None and is_blocked_ip(ip.sixtofour):
            return True
        if ip.teredo is not None and any(is_blocked_ip(v4) for v4 in ip.teredo):
            return True
        if ip.is_site_local:
            return True
    else:
        if any(ip in net for net in _EXTRA_BLOCKED_V4):
            return True

    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _getaddrinfo(host: str, port: int) -> list[str]:
    """Resolve `host` asynchronously; returns the IP strings. Patched in tests."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def _resolve_and_check(host: str, port: int) -> str:
    """Resolve `host`, validate every address, return the IP to pin to."""
    try:
        literal: IPAddress | None = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        ips: list[IPAddress] = [literal]
    else:
        try:
            raw = await _getaddrinfo(host, port)
        except (socket.gaierror, UnicodeError, OSError) as e:
            raise FetchError(f"Cannot resolve host: {host}") from e
        ips = []
        for addr in raw:
            # Strip an IPv6 zone id ("fe80::1%eth0") before parsing.
            ips.append(ipaddress.ip_address(addr.split("%", 1)[0]))
        if not ips:
            raise FetchError(f"Cannot resolve host: {host}")

    if not settings.allow_private_urls:
        for ip in ips:
            if is_blocked_ip(ip):
                raise PrivateAddressError(
                    f"URL resolves to non-public address {ip} "
                    "(set ALLOW_PRIVATE_URLS=true to allow)"
                )
    return str(ips[0])


def _validate_url(url: httpx.URL) -> None:
    if url.scheme not in ("http", "https"):
        raise InvalidURLError(f"Only http/https URLs are allowed, got {url.scheme!r}")
    if not url.host:
        raise InvalidURLError("URL has no hostname")
    if url.userinfo:
        raise InvalidURLError("Credentials in URLs are not allowed")


def precheck_url(url: str) -> None:
    """Cheap, DNS-free pre-screen run before an item is created.

    Rejects invalid schemes, credentials, IP literals in blocked ranges and
    obvious local hostnames. Hostnames that merely *resolve* to private
    addresses are still caught by the full check inside `safe_fetch`.
    """
    parsed = httpx.URL(url)
    _validate_url(parsed)
    if settings.allow_private_urls:
        return
    host = parsed.host.rstrip(".").lower()
    try:
        literal: IPAddress | None = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if is_blocked_ip(literal):
            raise PrivateAddressError(
                f"URL points to non-public address {literal} "
                "(set ALLOW_PRIVATE_URLS=true to allow)"
            )
        return
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise PrivateAddressError(
            f"URL points to a local hostname {host} (set ALLOW_PRIVATE_URLS=true to allow)"
        )


# ---------------------------------------------------------------------------
# Pinned transport
# ---------------------------------------------------------------------------


def _make_inner_transport() -> httpx.AsyncBaseTransport:
    """The real network transport. Patched in tests with an httpx.MockTransport."""
    return httpx.AsyncHTTPTransport(retries=0, http2=False, trust_env=False)


class _PinnedTransport(httpx.AsyncBaseTransport):
    """
    Sends every request to a fixed, pre-validated IP address.

    The URL host is replaced by the IP literal so the HTTP stack never does its
    own DNS lookup. The `Host` header (set by httpx from the original URL) is
    kept, and the `sni_hostname` request extension makes httpcore use the real
    hostname for TLS SNI *and* certificate hostname verification.
    """

    def __init__(self, hostname: str, ip: str):
        self._hostname = hostname
        self._ip = ip
        self._inner = _make_inner_transport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.raw_host.decode("ascii") != self._hostname:
            # Defensive: this transport must only ever talk to the host it was
            # validated for (redirects are handled outside, one client per hop).
            raise PrivateAddressError("Pinned transport used for a different host")
        if "Host" not in request.headers:
            request.headers["Host"] = request.url.netloc.decode("ascii")
        request.url = request.url.copy_with(host=self._ip)
        request.extensions = {**request.extensions, "sni_hostname": self._hostname}
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


# ---------------------------------------------------------------------------
# Body reading with bounded decompression
# ---------------------------------------------------------------------------


class _BoundedDecoder:
    """Decodes identity/gzip/deflate while never producing more than `limit` bytes."""

    def __init__(self, encoding: str, limit: int):
        self._limit = limit
        self._size = 0
        self._chunks: list[bytes] = []
        self._encoding = encoding
        self._first = True
        if encoding in ("", "identity"):
            self._d = None
        elif encoding in ("gzip", "x-gzip"):
            self._d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif encoding == "deflate":
            self._d = zlib.decompressobj()  # zlib-wrapped; raw fallback below
        else:
            raise FetchError(f"Unsupported content encoding: {encoding!r}")

    def _append(self, data: bytes) -> None:
        self._size += len(data)
        if self._size > self._limit:
            raise ResponseTooLargeError(f"Response exceeds {self._limit} bytes")
        if data:
            self._chunks.append(data)

    def feed(self, data: bytes) -> None:
        if self._d is None:
            self._append(data)
            return
        if self._first and self._encoding == "deflate":
            self._first = False
            try:
                probe = zlib.decompressobj()
                probe.decompress(data[:2])
            except zlib.error:
                self._d = zlib.decompressobj(-zlib.MAX_WBITS)  # raw deflate
        buf = data
        try:
            while buf:
                # +1 so that hitting the limit is detectable without inflating more.
                out = self._d.decompress(buf, self._limit - self._size + 1)
                self._append(out)
                tail = self._d.unconsumed_tail
                if not out and tail == buf:
                    # No progress: never leave input for flush(), which is unbounded.
                    raise FetchError(f"Corrupt {self._encoding} body")
                buf = tail
        except zlib.error as e:
            raise FetchError(f"Corrupt {self._encoding} body") from e

    def finish(self) -> bytes:
        if self._d is not None:
            try:
                # flush() has no max_length. feed() always drains unconsumed_tail,
                # so only already-buffered output (bounded) can remain here.
                if self._d.unconsumed_tail:
                    raise FetchError(f"Corrupt {self._encoding} body")
                self._append(self._d.flush())
            except zlib.error as e:
                raise FetchError(f"Corrupt {self._encoding} body") from e
        return b"".join(self._chunks)


def _parse_content_type(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parts = [p.strip() for p in value.split(";")]
    media = parts[0].lower() or None
    charset = None
    for p in parts[1:]:
        key, _, val = p.partition("=")
        if key.strip().lower() == "charset" and val:
            charset = val.strip().strip('"').strip("'") or None
    return media, charset


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def safe_fetch(
    url: str,
    *,
    max_bytes: int | None = None,
    accept: set[str] | frozenset[str] | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> FetchResult:
    """
    Fetch `url` with SSRF protection (see module docstring).

    accept: additional content types allowed on top of DEFAULT_ACCEPTED_TYPES.
    etag / last_modified: conditional request; a 304 is returned as a result
    with `not_modified=True` and an empty body.

    Raises a FetchError subclass on any policy violation or HTTP error.
    """
    limit = settings.fetch_max_bytes if max_bytes is None else max_bytes
    allowed_types = DEFAULT_ACCEPTED_TYPES | {t.lower() for t in (accept or ())}
    try:
        async with asyncio.timeout(settings.fetch_total_timeout):
            return await _fetch(url, limit, allowed_types, etag, last_modified)
    except TimeoutError as e:
        raise FetchError(f"Fetch timed out after {settings.fetch_total_timeout}s") from e
    except httpx.HTTPError as e:
        raise FetchError(f"Fetch failed: {type(e).__name__}: {e}") from e


async def _fetch(
    url: str,
    limit: int,
    allowed_types: frozenset[str],
    etag: str | None,
    last_modified: str | None,
) -> FetchResult:
    try:
        current = httpx.URL(url)
    except (httpx.InvalidURL, TypeError, ValueError) as e:
        raise InvalidURLError(f"Invalid URL: {e}") from e

    headers = {
        "User-Agent": settings.fetch_user_agent,
        "Accept": ", ".join(sorted(allowed_types)) + ";q=1.0, */*;q=0.1",
        "Accept-Encoding": "gzip, deflate",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    timeout = httpx.Timeout(settings.fetch_read_timeout, connect=settings.fetch_connect_timeout)
    redirects: list[str] = []

    while True:
        _validate_url(current)
        host = current.raw_host.decode("ascii")  # IDNA-encoded, as used on the wire
        port = current.port or (443 if current.scheme == "https" else 80)
        ip = await _resolve_and_check(host, port)

        transport = _PinnedTransport(host, ip)
        async with httpx.AsyncClient(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            request = client.build_request("GET", current, headers=headers)
            response = await client.send(request, stream=True)
            try:
                if response.status_code in REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if not location:
                        raise FetchError(f"Redirect without Location from {current}")
                    if len(redirects) >= settings.fetch_max_redirects:
                        raise TooManyRedirectsError(
                            f"More than {settings.fetch_max_redirects} redirects"
                        )
                    try:
                        nxt = current.join(location.strip())
                    except (httpx.InvalidURL, ValueError) as e:
                        raise InvalidURLError(f"Invalid redirect target: {e}") from e
                    redirects.append(str(nxt))
                    current = nxt
                    continue

                return await _read_final(response, current, limit, allowed_types, redirects)
            finally:
                await response.aclose()


async def _read_final(
    response: httpx.Response,
    url: httpx.URL,
    limit: int,
    allowed_types: frozenset[str],
    redirects: list[str],
) -> FetchResult:
    status = response.status_code
    media, charset = _parse_content_type(response.headers.get("Content-Type"))
    common = {
        "status": status,
        "final_url": str(url),
        "headers": response.headers,
        "content_type": media,
        "charset": charset,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "redirects": redirects,
    }

    if status == 304:
        return FetchResult(body=b"", **common)
    if not 200 <= status < 300:
        raise FetchStatusError(status, str(url))
    if media not in allowed_types:
        raise UnsupportedContentTypeError(f"Content type {media!r} is not allowed")

    declared = response.headers.get("Content-Length")
    encoding = response.headers.get("Content-Encoding", "").strip().lower()
    if declared and declared.isdigit() and not encoding and int(declared) > limit:
        raise ResponseTooLargeError(f"Response exceeds {limit} bytes")

    if "," in encoding:
        raise FetchError(f"Unsupported content encoding: {encoding!r}")
    decoder = _BoundedDecoder(encoding, limit)
    async for chunk in response.aiter_raw():
        decoder.feed(chunk)
    return FetchResult(body=decoder.finish(), **common)
