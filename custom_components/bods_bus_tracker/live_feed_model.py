"""Pure helpers for shared BODS live-feed handling."""

from __future__ import annotations


def bods_payload_is_invalid_token(payload: bytes | str | None) -> bool:
    """Return True when BODS explicitly reports an invalid API token."""
    if payload is None:
        return False
    text = (
        payload.decode("utf-8", errors="ignore")
        if isinstance(payload, bytes)
        else payload
    )
    return "invalid token" in text.casefold()


def classify_bods_http_status(status: int) -> str:
    """Return a stable diagnostic label when only the HTTP status is known."""
    if status == 401:
        return "authentication_failed"
    if status == 403:
        return "access_forbidden"
    if status == 429:
        return "rate_limited"
    return f"http_{status}"


def classify_bods_http_response(
    status: int, payload: bytes | str | None = None
) -> str:
    """Classify a BODS response using both status and any explicit API error."""
    if status == 403 and bods_payload_is_invalid_token(payload):
        return "authentication_failed"
    return classify_bods_http_status(status)
