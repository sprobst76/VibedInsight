"""URL canonicalisation used for dedup hashing (ingest, watchlist)."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlparse

_DEFAULT_PORTS = {"http": 80, "https": 443}
_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref_src", "si"}


def _is_tracking(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("utm_") or lowered in _TRACKING_PARAMS


def normalize_url(url: str) -> str:
    """
    Canonical form of a URL for dedup hashing.

    - Lowercase scheme and host, drop the default port
    - Drop the fragment and trailing slash (the root path stays ``/``)
    - Keep the query string (it identifies content, e.g. ``watch?v=ID``),
      minus tracking parameters, with the remaining parameters sorted
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    netloc = host
    if parsed.port and parsed.port != _DEFAULT_PORTS.get(scheme):
        netloc = f"{host}:{parsed.port}"
    if parsed.username:
        auth = parsed.username + (f":{parsed.password}" if parsed.password else "")
        netloc = f"{auth}@{netloc}"

    path = parsed.path or "/"
    if path.endswith("/") and len(path) > 1:
        path = path[:-1]

    params = sorted(
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not _is_tracking(k)
    )
    query = f"?{urlencode(params)}" if params else ""
    return f"{scheme}://{netloc}{path}{query}"


def hash_url(url: str) -> str:
    """SHA256 of the normalised URL."""
    return hashlib.sha256(normalize_url(url).encode()).hexdigest()
