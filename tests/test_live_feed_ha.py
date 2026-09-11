"""Home Assistant tests for the shared BODS live-feed client."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from aiohttp import ClientConnectionError
import pytest

from custom_components.bods_bus_tracker.live_feed import (
    BODS_SHARED_CACHE_SECONDS,
    BODSLiveFeedClient,
    BODSLiveFeedResult,
)


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, payload: bytes = b"<Siri/>") -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def read(self) -> bytes:
        return self._payload


class FakeSession:
    """Record requests and return or raise a configured outcome."""

    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0
        self.urls: list[str] = []

    def get(self, url, **kwargs):
        self.calls += 1
        self.urls.append(url)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


async def test_success_is_cached_and_url_is_operator_filtered(hass) -> None:
    """One successful operator payload is shared until the cache expires."""
    session = FakeSession(FakeResponse(200, b"payload"))
    client = BODSLiveFeedClient(hass, "secret")

    with patch(
        "custom_components.bods_bus_tracker.live_feed.async_get_clientsession",
        return_value=session,
    ):
        first = await client.async_get_operator("ANUM")
        second = await client.async_get_operator("ANUM")

    assert first == BODSLiveFeedResult(payload=b"payload")
    assert second is first
    assert session.calls == 1
    assert "operatorRef=ANUM" in session.urls[0]
    assert "api_key=secret" in session.urls[0]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "authentication_failed"),
        (403, "access_forbidden"),
        (429, "rate_limited"),
        (500, "http_500"),
    ],
)
async def test_http_failures_are_cached_diagnostics(
    hass, status: int, expected: str
) -> None:
    """HTTP failures remain local diagnostic results, not client crashes."""
    session = FakeSession(FakeResponse(status, b"error"))
    client = BODSLiveFeedClient(hass, "secret")

    with patch(
        "custom_components.bods_bus_tracker.live_feed.async_get_clientsession",
        return_value=session,
    ):
        result = await client.async_get_operator("ANUM")

    assert result.payload is None
    assert result.error == expected


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError(), "timeout"),
        (ClientConnectionError("offline"), "connection_error"),
        (RuntimeError("unexpected"), "RuntimeError"),
    ],
)
async def test_transport_failures_are_contained(hass, error: Exception, expected: str) -> None:
    """Timeouts, connection failures and defensive exceptions stay local."""
    session = FakeSession(error)
    client = BODSLiveFeedClient(hass, "secret")

    with patch(
        "custom_components.bods_bus_tracker.live_feed.async_get_clientsession",
        return_value=session,
    ):
        result = await client.async_get_operator("ANUM")

    assert result == BODSLiveFeedResult(payload=None, error=expected)


async def test_concurrent_same_operator_is_deduplicated(hass) -> None:
    """Concurrent stop coordinators share one in-flight operator request."""
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_fetch(operator: str) -> BODSLiveFeedResult:
        entered.set()
        await release.wait()
        result = BODSLiveFeedResult(payload=operator.encode())
        client._cache[operator] = (
            asyncio.get_running_loop().time(),
            result,
        )
        return result

    client = BODSLiveFeedClient(hass, "secret")
    with patch.object(client, "_async_fetch_operator", side_effect=slow_fetch) as fetch:
        task1 = asyncio.create_task(client.async_get_operator("ANUM"))
        await entered.wait()
        task2 = asyncio.create_task(client.async_get_operator("ANUM"))
        await asyncio.sleep(0)
        release.set()
        first, second = await asyncio.gather(task1, task2)

    assert first == second
    assert fetch.call_count == 1
    assert client._inflight == {}


async def test_expired_cache_is_not_reused(hass) -> None:
    """Cache entries older than the sharing window are ignored."""
    client = BODSLiveFeedClient(hass, "secret")
    loop = asyncio.get_running_loop()
    client._cache["ANUM"] = (
        loop.time() - BODS_SHARED_CACHE_SECONDS - 1,
        BODSLiveFeedResult(payload=b"old"),
    )

    assert client._cached("ANUM") is None


async def test_close_cancels_inflight_and_clears_cache(hass) -> None:
    """Unload cleanup cannot leave background feed tasks or cached payloads."""
    client = BODSLiveFeedClient(hass, "secret")
    client._cache["ANUM"] = (
        asyncio.get_running_loop().time(),
        BODSLiveFeedResult(payload=b"cached"),
    )

    started = asyncio.Event()

    async def sleeper() -> BODSLiveFeedResult:
        started.set()
        await asyncio.sleep(3600)
        return BODSLiveFeedResult(payload=b"never")

    task = asyncio.create_task(sleeper())
    await started.wait()
    client._inflight["ANUM"] = task

    await client.async_close()

    assert task.cancelled()
    assert client._inflight == {}
    assert client._cache == {}
