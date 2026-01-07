from urllib.parse import urlparse

import httpx
import trafilatura


async def extract_from_url(url: str) -> dict:
    """
    Extract article content from a URL.
    Returns title, text, and source domain.
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
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
