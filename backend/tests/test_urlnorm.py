import pytest

from app.services.urlnorm import hash_url, normalize_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("HTTP://X.de:80/a/", "http://x.de/a"),
        ("https://x.de:443/a", "https://x.de/a"),
        ("https://x.de:8443/a", "https://x.de:8443/a"),
        ("https://x.de/a#frag", "https://x.de/a"),
        ("https://x.de/", "https://x.de/"),
        ("https://x.de", "https://x.de/"),
        ("https://x.de/a?utm_source=n&b=2&a=1", "https://x.de/a?a=1&b=2"),
        ("https://x.de/a?fbclid=zz", "https://x.de/a"),
        ("https://x.de/?a=1", "https://x.de/?a=1"),
        ("https://www.youtube.com/watch?v=A", "https://www.youtube.com/watch?v=A"),
    ],
)
def test_normalize(raw, expected):
    assert normalize_url(raw) == expected


def test_query_identifies_content():
    assert hash_url("https://youtube.com/watch?v=A") != hash_url("https://youtube.com/watch?v=B")


def test_param_order_and_tracking_ignored():
    assert hash_url("https://x.de/a?b=2&a=1&utm_medium=m") == hash_url("https://x.de/a?a=1&b=2")
