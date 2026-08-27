"""Data coordinator for BODS Bus Tracker."""

from __future__ import annotations

import asyncio
import logging
import math
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ServiceSpec,
    build_gtfs_index,
    make_snapshot,
    parse_service_key,
    parse_siri,
)
from .const import (
    BODS_VEHICLE_URL,
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_VIEW,
    CONF_WALKING_TIME,
    CONF_WALKING_TIME_ENTITY,
    DEFAULT_DYNAMIC_WALKING_TIME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_STOP_VIEW,
    DEFAULT_WALKING_TIME,
    DYNAMIC_WALKING_STALE_SECONDS,
    LOCAL_TIME_ZONE,
    MAX_LIVE_AGE_SECONDS,
    MAX_WALKING_TIME,
    STOP_VIEW_ARRIVALS,
    VERSION,
)
from .gtfs import async_ensure_gtfs
from .stop_view import apply_stop_view
from .walking import apply_walking_guidance, normalise_dynamic_walking_minutes

_LOGGER = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo(LOCAL_TIME_ZONE)


def _path_mtime(path: Path) -> float | None:
    """Return a path modification time outside Home Assistant's event loop."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


class BODSBusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate BODS vehicle data and GTFS timetable data for one stop."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        self.entry = entry
        self.subentry = subentry
        self.api_key: str = entry.data[CONF_API_KEY]
        self.region: str = subentry.data[CONF_REGION]
        self.stop_atco: str = subentry.data[CONF_STOP_ATCO]
        self.stop_name: str = subentry.data[CONF_STOP_NAME]
        self.stop_view: str = str(
            subentry.data.get(CONF_STOP_VIEW, DEFAULT_STOP_VIEW)
        )
        self.walking_time: int = int(
            subentry.data.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
        )
        self.dynamic_walking_time: bool = bool(
            subentry.data.get(
                CONF_DYNAMIC_WALKING_TIME, DEFAULT_DYNAMIC_WALKING_TIME
            )
        )
        self.walking_time_entity: str | None = (
            str(subentry.data.get(CONF_WALKING_TIME_ENTITY) or "").strip() or None
        )
        self.services: list[ServiceSpec] = [
            parse_service_key(value) for value in subentry.data[CONF_SERVICES]
        ]
        poll_interval = int(
            subentry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        self.gtfs_path: Path | None = None
        self._trips = []
        self._gtfs_info: dict[str, object] = {}
        self._service_date = None
        self._last_gtfs_check: datetime | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"BODS Bus Tracker {entry.entry_id} {subentry.subentry_id}",
            update_interval=timedelta(seconds=poll_interval),
        )

    async def async_prepare(self) -> None:
        """Prepare GTFS data before first coordinator refresh."""
        self.gtfs_path = await async_ensure_gtfs(self.hass, self.region)
        await self._async_rebuild_gtfs(datetime.now(LOCAL_TZ).date())

    async def _async_rebuild_gtfs(self, service_date) -> None:
        assert self.gtfs_path is not None
        self._trips, self._gtfs_info = await self.hass.async_add_executor_job(
            build_gtfs_index,
            self.gtfs_path,
            service_date,
            self.stop_atco,
            self.services,
        )
        self._service_date = service_date
        self._last_gtfs_check = datetime.now(LOCAL_TZ)
        _LOGGER.debug(
            "Built GTFS index for %s/%s: %s target trips",
            self.stop_atco,
            service_date,
            self._gtfs_info.get("target_trip_count"),
        )

    async def _async_refresh_gtfs_if_needed(self, now: datetime) -> None:
        if self._service_date != now.date():
            await self._async_rebuild_gtfs(now.date())
            return
        if self._last_gtfs_check and now - self._last_gtfs_check < timedelta(hours=1):
            return
        old_path = self.gtfs_path
        old_mtime = (
            await self.hass.async_add_executor_job(_path_mtime, old_path)
            if old_path is not None
            else None
        )
        self.gtfs_path = await async_ensure_gtfs(self.hass, self.region)
        self._last_gtfs_check = now
        new_mtime = await self.hass.async_add_executor_job(_path_mtime, self.gtfs_path)
        if old_mtime is None or new_mtime != old_mtime:
            await self._async_rebuild_gtfs(now.date())

    async def _async_fetch_service(self, service: ServiceSpec) -> bytes:
        session = async_get_clientsession(self.hass)
        params = {
            "operatorRef": service.operator_noc,
            "lineRef": service.route,
            "api_key": self.api_key,
        }
        url = f"{BODS_VEHICLE_URL}?{urllib.parse.urlencode(params)}"
        async with session.get(
            url,
            timeout=ClientTimeout(total=25),
            headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
        ) as response:
            response.raise_for_status()
            return await response.read()

    def _walking_guidance_values(
        self, now: datetime
    ) -> tuple[int, str, float | None, bool, str]:
        """Resolve effective walking minutes without contacting routing providers."""
        static_minutes = max(0, int(self.walking_time))
        if not self.dynamic_walking_time:
            return (
                static_minutes,
                "static" if static_minutes > 0 else "disabled",
                None,
                False,
                "disabled",
            )

        entity_id = self.walking_time_entity
        if not entity_id:
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "not_configured",
            )

        state = self.hass.states.get(entity_id)
        if state is None:
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "missing",
            )
        if state.state == "unknown":
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "unknown",
            )
        if state.state == "unavailable":
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "unavailable",
            )

        reported = getattr(state, "last_reported", None) or state.last_updated
        if reported is not None:
            reported_local = reported.astimezone(now.tzinfo) if now.tzinfo else reported
            if (now - reported_local).total_seconds() > DYNAMIC_WALKING_STALE_SECONDS:
                return (
                    static_minutes,
                    "static_fallback" if static_minutes > 0 else "disabled",
                    None,
                    True,
                    "stale",
                )

        dynamic_minutes = normalise_dynamic_walking_minutes(
            state.state,
            state.attributes.get("unit_of_measurement"),
            MAX_WALKING_TIME,
        )
        if dynamic_minutes is None:
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "invalid",
            )

        effective_minutes = max(0, math.ceil(dynamic_minutes))
        return effective_minutes, "dynamic", dynamic_minutes, False, "ok"

    async def _async_update_data(self) -> dict[str, Any]:
        now = datetime.now(LOCAL_TZ)
        try:
            await self._async_refresh_gtfs_if_needed(now)
        except Exception as exc:
            raise UpdateFailed(f"Unable to prepare BODS timetable data: {exc}") from exc

        results = await asyncio.gather(
            *(self._async_fetch_service(service) for service in self.services),
            return_exceptions=True,
        )

        vehicles = []
        route_errors: dict[str, str] = {}
        warnings: list[str] = []
        for service, result in zip(self.services, results, strict=True):
            if isinstance(result, BaseException):
                if isinstance(result, ClientResponseError):
                    if result.status in (401, 403):
                        route_errors[service.key] = "authentication_failed"
                    else:
                        route_errors[service.key] = f"http_{result.status}"
                elif isinstance(result, TimeoutError):
                    route_errors[service.key] = "timeout"
                elif isinstance(result, ClientError):
                    route_errors[service.key] = "connection_error"
                else:
                    route_errors[service.key] = type(result).__name__
                continue
            try:
                parsed, _timestamp, parsed_warnings = await self.hass.async_add_executor_job(
                    parse_siri,
                    result,
                    self.services,
                )
                vehicles.extend(parsed)
                warnings.extend(parsed_warnings)
            except Exception as exc:
                route_errors[service.key] = f"parse_error: {exc}"

        if self.services and all(
            route_errors.get(service.key) == "authentication_failed"
            for service in self.services
        ):
            raise ConfigEntryAuthFailed("BODS API key was rejected")

        snapshot = await self.hass.async_add_executor_job(
            make_snapshot,
            self._trips,
            self._gtfs_info,
            vehicles,
            now,
            self.stop_atco,
            self.stop_name,
            self.services,
            route_errors,
            warnings,
            MAX_LIVE_AGE_SECONDS,
        )
        snapshot = await self.hass.async_add_executor_job(
            apply_stop_view,
            snapshot,
            self._trips,
            vehicles,
            now,
            self.stop_atco,
            self.services,
            self.stop_view,
            MAX_LIVE_AGE_SECONDS,
        )

        # Walking guidance is intentionally tied to a boardable departure. In arrivals
        # mode it is disabled; in both mode Next bus remains the next departure.
        if self.stop_view == STOP_VIEW_ARRIVALS:
            return snapshot

        (
            walking_minutes,
            walking_mode,
            dynamic_minutes,
            walking_fallback,
            source_status,
        ) = self._walking_guidance_values(now)
        return apply_walking_guidance(
            snapshot,
            now,
            walking_minutes,
            walking_mode=walking_mode,
            walking_time_entity=(
                self.walking_time_entity if self.dynamic_walking_time else None
            ),
            walking_dynamic_minutes=dynamic_minutes,
            walking_fallback=walking_fallback,
            walking_source_status=source_status,
        )
