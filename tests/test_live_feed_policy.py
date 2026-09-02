"""Shared BODS live-feed policy tests."""

from custom_components.bods_bus_tracker.live_feed import (
    BODS_MIN_REQUEST_INTERVAL_SECONDS,
    BODS_SHARED_CACHE_SECONDS,
)
from custom_components.bods_bus_tracker.live_feed_model import classify_bods_http_status


def test_shared_feed_keeps_requests_inside_bods_rate_guidance() -> None:
    assert BODS_MIN_REQUEST_INTERVAL_SECONDS > 5.0
    assert BODS_SHARED_CACHE_SECONDS >= 15.0


def test_only_401_is_classified_as_authentication_failure() -> None:
    assert classify_bods_http_status(401) == "authentication_failed"
    assert classify_bods_http_status(403) == "access_forbidden"
    assert classify_bods_http_status(429) == "rate_limited"
    assert classify_bods_http_status(503) == "http_503"
