"""HTTP helpers that allow http and https only."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import requests

_MAX_HOPS = 10


class UnsafeURL(ValueError):
    """The URL scheme is not http or https."""


def check_url(url: str) -> None:
    scheme = urlparse(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise UnsafeURL(f"refusing URL scheme {scheme or '(none)'}")


def get(url: str, **kwargs):
    """GET ``url``. Check the scheme, then check it again on every redirect."""
    kwargs.pop("allow_redirects", None)
    timeout = kwargs.pop("timeout", 30)
    current = url
    for _ in range(_MAX_HOPS):
        check_url(current)
        response = requests.get(current, allow_redirects=False, timeout=timeout, **kwargs)
        location = response.headers.get("Location") if response.is_redirect else None
        if not location:
            return response
        current = urljoin(response.url, location)
    check_url(current)
    raise UnsafeURL("too many redirects")


def post(url: str, **kwargs):
    """POST ``url``. Check the scheme and do not follow redirects."""
    check_url(url)
    kwargs.pop("allow_redirects", None)
    timeout = kwargs.pop("timeout", 60)
    return requests.post(url, allow_redirects=False, timeout=timeout, **kwargs)
