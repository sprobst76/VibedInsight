"""
Tests for the SSRF-safe fetcher (app.services.fetcher).

No network: DNS is replaced by a fake resolver and the socket-level transport
by an httpx.MockTransport that records which IP each request was pinned to.
"""

import gzip
import ipaddress

import httpx
import pytest

from app.config import settings
from app.services import extractor, fetcher
from app.services.fetcher import (
    FetchError,
    FetchStatusError,
    InvalidURLError,
    PrivateAddressError,
    ResponseTooLargeError,
    TooManyRedirectsError,
    UnsupportedContentTypeError,
    is_blocked_ip,
    safe_fetch,
)

PUBLIC_IP = "93.184.216.34"
HTML = {"Content-Type": "text/html; charset=utf-8"}


class FakeNet:
    """Fake DNS + fake wire. `routes` maps hostname -> handler(request)."""

    def __init__(self, dns=None, routes=None):
        self.dns = dns or {}
        self.routes = routes or {}
        self.resolve_calls: list[str] = []
        self.sent: list[httpx.Request] = []

    async def resolve(self, host, port):
        self.resolve_calls.append(host)
        answer = self.dns.get(host, [PUBLIC_IP])
        return answer(len(self.resolve_calls)) if callable(answer) else answer

    def transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.sent.append(request)
            host = request.headers["Host"].split(":")[0]
            route = self.routes.get(host)
            if route is None:
                return ok()
            return route(request)

        return httpx.MockTransport(handler)


@pytest.fixture
def net(monkeypatch):
    n = FakeNet()
    monkeypatch.setattr(settings, "allow_private_urls", False)
    monkeypatch.setattr(fetcher, "_getaddrinfo", n.resolve)
    monkeypatch.setattr(fetcher, "_make_inner_transport", n.transport)
    return n


def ok(body=b"<p>ok</p>", headers=None, status=200):
    """Streaming response (like a real network transport — not pre-read)."""

    async def stream():
        yield body

    return httpx.Response(status, headers=headers or HTML, content=stream())


def redirect_to(location, status=302):
    return lambda request: httpx.Response(status, headers={"Location": location})


# ---------------------------------------------------------------------------
# Allowed path + pinning
# ---------------------------------------------------------------------------


async def test_allowed_fetch_is_pinned_with_host_and_sni(net):
    result = await safe_fetch("https://example.com/article?id=1")

    assert result.status == 200
    assert result.final_url == "https://example.com/article?id=1"
    assert result.text == "<p>ok</p>"
    assert result.content_type == "text/html"

    sent = net.sent[0]
    assert sent.url.host == PUBLIC_IP  # connection goes to the checked IP
    assert sent.url.raw_path == b"/article?id=1"
    assert sent.headers["Host"] == "example.com"
    assert sent.extensions["sni_hostname"] == "example.com"  # TLS SNI + cert check


async def test_dns_rebinding_has_no_effect(net):
    # First lookup public, every later lookup private: the HTTP layer must never
    # resolve again, so the request still goes to the checked public IP.
    net.dns["rebind.example"] = lambda n: [PUBLIC_IP] if n == 1 else ["127.0.0.1"]

    result = await safe_fetch("http://rebind.example/")

    assert result.status == 200
    assert net.resolve_calls == ["rebind.example"]
    assert [r.url.host for r in net.sent] == [PUBLIC_IP]


async def test_rebinding_on_redirect_hop_is_rejected(net):
    net.dns["rebind.example"] = lambda n: [PUBLIC_IP] if n == 1 else ["10.0.0.5"]
    net.routes["rebind.example"] = lambda req: (
        httpx.Response(302, headers={"Location": "/next"}) if req.url.path == "/" else ok(b"x")
    )

    with pytest.raises(PrivateAddressError):
        await safe_fetch("http://rebind.example/")
    assert len(net.sent) == 1


# ---------------------------------------------------------------------------
# Redirects to internal addresses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
        "http://100.64.1.1/",
        "http://[64:ff9b::7f00:1]/",
    ],
)
async def test_redirect_to_internal_address_is_rejected(net, target):
    net.routes["example.com"] = redirect_to(target)

    with pytest.raises(PrivateAddressError):
        await safe_fetch("http://example.com/")
    assert len(net.sent) == 1  # internal target never contacted


async def test_redirect_to_hostname_resolving_private_is_rejected(net):
    net.dns["internal.example"] = [PUBLIC_IP, "192.168.1.10"]  # one bad IP is enough
    net.routes["example.com"] = redirect_to("http://internal.example/")

    with pytest.raises(PrivateAddressError):
        await safe_fetch("http://example.com/")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://a@127.0.0.1/",
        "http://2130706433/",  # decimal 127.0.0.1 — resolver normalizes it
        "http://localhost/",
    ],
)
async def test_direct_internal_urls_are_rejected(net, url):
    net.dns["2130706433"] = ["127.0.0.1"]
    net.dns["localhost"] = ["127.0.0.1", "::1"]
    with pytest.raises((PrivateAddressError, InvalidURLError)):
        await safe_fetch(url)
    assert net.sent == []


async def test_relative_redirect_is_resolved_against_current_url(net):
    net.routes["example.com"] = lambda req: (
        httpx.Response(301, headers={"Location": "../b/c?x=1"})
        if req.url.path == "/a/start"
        else ok(b"done")
    )

    result = await safe_fetch("http://example.com/a/start")

    assert result.final_url == "http://example.com/b/c?x=1"
    assert result.redirects == ["http://example.com/b/c?x=1"]
    assert result.body == b"done"


async def test_redirect_to_non_http_scheme_is_rejected(net):
    net.routes["example.com"] = redirect_to("file:///etc/passwd")
    with pytest.raises(InvalidURLError):
        await safe_fetch("http://example.com/")


async def test_more_than_five_redirects_aborts(net):
    counter = {"n": 0}

    def loop(request):
        counter["n"] += 1
        return httpx.Response(302, headers={"Location": f"/hop{counter['n']}"})

    net.routes["example.com"] = loop
    with pytest.raises(TooManyRedirectsError):
        await safe_fetch("http://example.com/")
    assert len(net.sent) == 6  # original + 5 followed hops, 6th redirect refused


async def test_five_redirects_are_allowed(net):
    def chain(request):
        n = int(request.url.path.strip("/") or 0)
        if n < 5:
            return httpx.Response(302, headers={"Location": f"/{n + 1}"})
        return ok(b"end")

    net.routes["example.com"] = chain
    result = await safe_fetch("http://example.com/")
    assert result.body == b"end"
    assert len(result.redirects) == 5


# ---------------------------------------------------------------------------
# Size limit + content type
# ---------------------------------------------------------------------------


async def test_body_over_limit_is_aborted_without_content_length(net):
    big = b"a" * (5 * 1024 * 1024 + 1)

    async def stream():
        for i in range(0, len(big), 65536):
            yield big[i : i + 65536]

    net.routes["example.com"] = lambda req: httpx.Response(200, headers=HTML, content=stream())
    with pytest.raises(ResponseTooLargeError):
        await safe_fetch("http://example.com/")


async def test_declared_content_length_over_limit_is_rejected(net):
    net.routes["example.com"] = lambda req: httpx.Response(
        200, headers={**HTML, "Content-Length": str(10 * 1024 * 1024)}, content=b""
    )
    with pytest.raises(ResponseTooLargeError):
        await safe_fetch("http://example.com/")


async def test_gzip_bomb_is_limited_on_decoded_bytes(net):
    bomb = gzip.compress(b"\0" * (20 * 1024 * 1024))  # ~20 KB compressed
    assert len(bomb) < 100_000
    net.routes["example.com"] = lambda req: ok(bomb, {**HTML, "Content-Encoding": "gzip"})
    with pytest.raises(ResponseTooLargeError):
        await safe_fetch("http://example.com/")


async def test_gzip_body_is_decoded(net):
    net.routes["example.com"] = lambda req: ok(
        gzip.compress(b"hello"), {**HTML, "Content-Encoding": "gzip"}
    )
    result = await safe_fetch("http://example.com/")
    assert result.body == b"hello"


async def test_image_png_is_rejected(net):
    net.routes["example.com"] = lambda req: httpx.Response(
        200, headers={"Content-Type": "image/png"}, content=b"\x89PNG"
    )
    with pytest.raises(UnsupportedContentTypeError):
        await safe_fetch("http://example.com/")


async def test_accept_extends_allowlist(net):
    net.routes["example.com"] = lambda req: ok(b"<rss/>", {"Content-Type": "application/rss+xml"})
    result = await safe_fetch("http://example.com/feed", accept={"application/rss+xml"})
    assert result.body == b"<rss/>"


async def test_http_error_status_raises(net):
    net.routes["example.com"] = lambda req: httpx.Response(404, headers=HTML)
    with pytest.raises(FetchStatusError) as exc:
        await safe_fetch("http://example.com/")
    assert exc.value.status == 404


async def test_conditional_request_returns_not_modified(net):
    def handler(req):
        assert req.headers["If-None-Match"] == '"v1"'
        return httpx.Response(304, headers={"ETag": '"v1"'})

    net.routes["example.com"] = handler
    result = await safe_fetch("http://example.com/", etag='"v1"')
    assert result.not_modified
    assert result.etag == '"v1"'


async def test_transport_errors_become_fetch_errors(monkeypatch, net):
    def boom(request):
        raise httpx.ConnectError("certificate verify failed")

    monkeypatch.setattr(fetcher, "_make_inner_transport", lambda: httpx.MockTransport(boom))
    with pytest.raises(FetchError):
        await safe_fetch("https://example.com/")


# ---------------------------------------------------------------------------
# Dev switch + IP classification
# ---------------------------------------------------------------------------


async def test_allow_private_urls_permits_localhost(net, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_urls", True)
    net.dns["localhost"] = ["127.0.0.1"]

    result = await safe_fetch("http://localhost:8080/page")

    assert result.status == 200
    assert net.sent[0].url.host == "127.0.0.1"
    assert net.sent[0].url.port == 8080
    assert net.sent[0].headers["Host"] == "localhost:8080"


@pytest.mark.parametrize(
    "ip,blocked",
    [
        ("8.8.8.8", False),
        ("2606:4700:4700::1111", False),
        ("10.1.2.3", True),
        ("172.16.0.1", True),
        ("192.168.0.1", True),
        ("127.0.0.1", True),
        ("169.254.169.254", True),
        ("0.1.2.3", True),
        ("100.100.100.100", True),
        ("224.0.0.1", True),
        ("255.255.255.255", True),
        ("::", True),
        ("::1", True),
        ("fe80::1", True),
        ("fc00::1", True),
        ("ff02::1", True),
        ("::ffff:10.0.0.1", True),
        ("2002:7f00:1::", True),  # 6to4 wrapping 127.0.0.1
    ],
)
def test_is_blocked_ip(ip, blocked):
    assert is_blocked_ip(ipaddress.ip_address(ip)) is blocked


# ---------------------------------------------------------------------------
# Extractor integration
# ---------------------------------------------------------------------------


async def test_extractor_uses_safe_fetch(net):
    page = (
        b"<html><head><title>Hello World</title></head><body><article>"
        + b"<p>This is a reasonably long paragraph of article text. </p>" * 20
        + b"</article></body></html>"
    )
    net.routes["www.example.com"] = lambda req: ok(page)

    data = await extractor.extract_from_url("https://www.example.com/post")

    assert data["title"] == "Hello World"
    assert "reasonably long paragraph" in data["text"]
    assert data["source"] == "example.com"


async def test_extractor_rejects_private_url(net):
    with pytest.raises(extractor.PrivateAddressError):
        await extractor.extract_from_url("http://127.0.0.1/")
