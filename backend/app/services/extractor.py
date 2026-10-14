import asyncio
from urllib.parse import urlparse

import trafilatura

from app.services.fetcher import PrivateAddressError, safe_fetch

__all__ = ["PrivateAddressError", "extract_from_url"]


def _extract(html: str) -> tuple[str | None, str | None]:
    """CPU-bound trafilatura work — runs in a worker thread."""
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
    )
    metadata = trafilatura.extract_metadata(html)
    return text, (metadata.title if metadata else None)


async def extract_from_url(url: str) -> dict:
    """
    Extract article content from a URL.
    Returns title, text, and source domain.

    Fetching goes through the SSRF-safe fetcher (raises a FetchError subclass,
    e.g. PrivateAddressError, on policy violations). Parsing runs off the
    event loop so large pages don't stall other requests.
    """
    result = await safe_fetch(url)

    text, title = await asyncio.to_thread(_extract, result.text)

    # Source domain of the originally submitted URL (as before)
    source = urlparse(url).netloc.replace("www.", "")

    return {
        "title": title,
        "text": text,
        "source": source,
    }
