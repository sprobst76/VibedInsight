import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import trafilatura

from app.config import settings


class PrivateAddressError(ValueError):
    """URL resolves to a private/loopback address (SSRF guard)."""


def _check_url_allowed(url: str) -> None:
    """
    Reject URLs that resolve to private, loopback, or link-local addresses,
    unless ALLOW_PRIVATE_URLS=true (e.g. to save pages from your own LAN).
    """
    if settings.allow_private_urls:
        return

    host = urlparse(url).hostname
    if not host:
        raise PrivateAddressError("URL has no hostname")

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise PrivateAddressError(f"Cannot resolve host: {host}") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise PrivateAddressError(
                f"URL resolves to non-public address {ip} (set ALLOW_PRIVATE_URLS=true to allow)"
            )


async def extract_from_url(url: str) -> dict:
    """
    Extract article content from a URL.
    Returns title, text, and source domain.
    """
    _check_url_allowed(url)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=30.0), follow_redirects=True
    ) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; VibedInsight/1.0; +https://github.com/vibedinsight)"
            },
        )
        response.raise_for_status()
        html = response.text

    # Extract main content using trafilatura
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )

    # Get metadata
    metadata = trafilatura.extract_metadata(html)

    # Parse domain
    parsed_url = urlparse(url)
    source = parsed_url.netloc.replace("www.", "")

    return {
        "title": metadata.title if metadata else None,
        "text": extracted,
        "source": source,
    }
