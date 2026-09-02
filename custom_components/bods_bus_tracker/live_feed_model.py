"""Pure helpers for shared BODS live-feed handling."""

from __future__ import annotations


def classify_bods_http_status(status: int) -> str:
    """Return a stable diagnostic label for a BODS HTTP response."""
    if status == 401:
        return "authentication_failed"
    if status == 403:
        return "access_forbidden"
    if status == 429:
        return "rate_limited"
    return f"http_{status}"
