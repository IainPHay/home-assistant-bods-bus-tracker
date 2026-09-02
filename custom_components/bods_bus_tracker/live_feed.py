"""Shared, rate-limited live BODS vehicle feed client."""

from __future__ import annotations

import asyncio
import urllib.parse
from dataclasses import dataclass

from aiohttp import ClientError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BODS_VEHICLE_URL, VERSION
from .live_feed_model import classify_bods_http_status

BODS_MIN_REQUEST_INTERVAL_SECONDS = 6.0
BODS_SHARED_CACHE_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class BODSLiveFeedResult:
    """One cached operator-level BODS live-feed result."""

    payload: bytes | None
    error: str | None = None


class BODSLiveFeedClient:
    """Share BODS operator feeds across all configured stop coordinators."""

    def __init__(self, hass: HomeAssistant, api_key: str) -> None:
        self.hass = hass
        self.api_key = api_key
        self._request_lock = asyncio.Lock()
        self._last_request_started: float | None = None
        self._cache: dict[str, tuple[float, BODSLiveFeedResult]] = {}
        self._inflight: dict[str, asyncio.Task[BODSLiveFeedResult]] = {}

    def _cached(self, operator_noc: str) -> BODSLiveFeedResult | None:
        cached = self._cache.get(operator_noc)
        if cached is None:
            return None
        cached_at, result = cached
        if asyncio.get_running_loop().time() - cached_at >= BODS_SHARED_CACHE_SECONDS:
            return None
        return result

    async def async_get_operator(self, operator_noc: str) -> BODSLiveFeedResult:
        """Return one operator feed, sharing cache and in-flight work."""
        if cached := self._cached(operator_noc):
            return cached

        task = self._inflight.get(operator_noc)
        if task is None:
            task = asyncio.create_task(
                self._async_fetch_operator(operator_noc),
                name=f"BODS live feed {operator_noc}",
            )
            self._inflight[operator_noc] = task

        try:
            return await task
        finally:
            if self._inflight.get(operator_noc) is task:
                self._inflight.pop(operator_noc, None)

    async def _async_fetch_operator(self, operator_noc: str) -> BODSLiveFeedResult:
        """Fetch and cache one operator-level feed with global request spacing."""
        async with self._request_lock:
            if cached := self._cached(operator_noc):
                return cached

            loop = asyncio.get_running_loop()
            if self._last_request_started is not None:
                wait_seconds = BODS_MIN_REQUEST_INTERVAL_SECONDS - (
                    loop.time() - self._last_request_started
                )
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            self._last_request_started = loop.time()
            session = async_get_clientsession(self.hass)
            params = {
                "operatorRef": operator_noc,
                "api_key": self.api_key,
            }
            url = f"{BODS_VEHICLE_URL}?{urllib.parse.urlencode(params)}"
            try:
                async with session.get(
                    url,
                    timeout=ClientTimeout(total=25),
                    headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
                ) as response:
                    payload = await response.read()
                    if response.status >= 400:
                        result = BODSLiveFeedResult(
                            payload=None,
                            error=classify_bods_http_status(response.status),
                        )
                    else:
                        result = BODSLiveFeedResult(payload=payload)
            except TimeoutError:
                result = BODSLiveFeedResult(payload=None, error="timeout")
            except ClientError:
                result = BODSLiveFeedResult(payload=None, error="connection_error")
            except Exception as exc:  # defensive: keep one feed failure local
                result = BODSLiveFeedResult(
                    payload=None,
                    error=type(exc).__name__,
                )

            self._cache[operator_noc] = (loop.time(), result)
            return result
