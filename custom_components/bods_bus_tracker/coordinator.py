"""Data coordinator for BODS Bus Tracker."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ServiceSpec,
    make_snapshot,
    parse_service_key,
    parse_siri,
)
from .const import (
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
    DOMAIN,
    DEFAULT_STOP_VIEW,
    DEFAULT_WALKING_TIME,
    DYNAMIC_WALKING_STALE_SECONDS,
    LOCAL_TIME_ZONE,
    MAX_LIVE_AGE_SECONDS,
    MAX_WALKING_TIME,
    STOP_VIEW_ARRIVALS,
)
from .gtfs import SharedGTFSRegionIndex
from .live_feed import BODSLiveFeedClient, BODSLiveFeedResult
from .stop_view import apply_stop_view
from .walking import apply_walking_guidance, normalise_dynamic_walking_minutes

_LOGGER = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo(LOCAL_TIME_ZONE)


class BODSBusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate BODS vehicle data and GTFS timetable data for one stop."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        live_feed: BODSLiveFeedClient,
        timetable: SharedGTFSRegionIndex,
    ) -> None:
        self.entry = entry
        self.subentry = subentry
        self.live_feed = live_feed
        self.timetable = timetable
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
        self._services_by_operator: dict[str, list[ServiceSpec]] = {}
        for service in self.services:
            self._services_by_operator.setdefault(service.operator_noc, []).append(service)
        poll_interval = int(
            subentry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        self._trips = []
        self._gtfs_info: dict[str, object] = {}
        self._service_date = None
        self._gtfs_generation: int | None = None
        self._gtfs_initial_source: str | None = None
        self._gtfs_initial_prepare_seconds: float | None = None
        self._last_live_health: str | None = None
        self._walking_entity_missing_count = 0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"BODS Bus Tracker {entry.entry_id} {subentry.subentry_id}",
            update_interval=timedelta(seconds=poll_interval),
        )

    async def async_prepare(self) -> None:
        """Prepare the stop-specific view of the shared regional GTFS index."""
        await self._async_sync_gtfs(datetime.now(LOCAL_TZ).date())

    async def _async_sync_gtfs(self, service_date) -> None:
        shared_trips, shared_info = await self.timetable.async_get(service_date)
        generation = int(shared_info.get("index_generation", 0))
        if self._service_date == service_date and self._gtfs_generation == generation:
            self._gtfs_info["index_last_source"] = shared_info.get("index_source")
            self._gtfs_info["index_last_prepare_seconds"] = shared_info.get(
                "index_prepare_seconds"
            )
            return

        selected = {(service.operator_noc, service.route) for service in self.services}
        self._trips = [
            trip
            for trip in shared_trips
            if (trip.operator_noc, trip.route) in selected
        ]
        if self._gtfs_initial_source is None:
            self._gtfs_initial_source = str(shared_info.get("index_source", "unknown"))
            initial_seconds = shared_info.get("index_prepare_seconds")
            self._gtfs_initial_prepare_seconds = (
                float(initial_seconds) if initial_seconds is not None else None
            )

        self._gtfs_info = {
            **shared_info,
            "relevant_trip_count": len(self._trips),
            "target_trip_count": sum(
                1 for trip in self._trips if trip.target(self.stop_atco) is not None
            ),
            "index_initial_source": self._gtfs_initial_source,
            "index_initial_prepare_seconds": self._gtfs_initial_prepare_seconds,
            "index_last_source": shared_info.get("index_source"),
            "index_last_prepare_seconds": shared_info.get("index_prepare_seconds"),
        }
        self._service_date = service_date
        self._gtfs_generation = generation
        _LOGGER.debug(
            "Loaded shared GTFS index for %s/%s: %s target trips (%s, %.3fs)",
            self.stop_atco,
            service_date,
            self._gtfs_info.get("target_trip_count"),
            shared_info.get("index_source"),
            float(shared_info.get("index_prepare_seconds", 0.0)),
        )

    async def _async_refresh_gtfs_if_needed(self, now: datetime) -> None:
        await self._async_sync_gtfs(now.date())

    def _log_live_health_transition(self, health: str) -> None:
        """Log live-data availability only when its state changes."""
        previous = self._last_live_health
        if health == previous:
            return

        self._last_live_health = health
        if health == "ok":
            if previous in {"degraded", "scheduled_only"}:
                _LOGGER.info(
                    "%s BODS live vehicle data is available again",
                    self.stop_name,
                )
            return

        if health == "degraded":
            _LOGGER.warning(
                "%s BODS live vehicle data is degraded; timetable fallback will be used where needed",
                self.stop_name,
            )
        elif health == "scheduled_only":
            _LOGGER.warning(
                "%s BODS live vehicle data is unavailable; using timetable data",
                self.stop_name,
            )

    @property
    def _walking_entity_issue_id(self) -> str:
        """Return the repair issue ID for this stop's routed walking source."""
        return f"walking_time_entity_missing_{self.subentry.subentry_id}"

    def _clear_walking_entity_issue(self) -> None:
        """Remove an obsolete routed-walking repair issue."""
        self._walking_entity_missing_count = 0
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            self._walking_entity_issue_id,
        )

    def _note_missing_walking_entity(self, entity_id: str) -> None:
        """Create one actionable Repair for a persistently missing source entity."""
        self._walking_entity_missing_count += 1
        if (
            self.hass.state is not CoreState.running
            or self._walking_entity_missing_count < 2
        ):
            return

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._walking_entity_issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="walking_time_entity_missing",
            translation_placeholders={
                "entity_id": entity_id,
                "stop": self.stop_name,
            },
        )

    def _walking_guidance_values(
        self, now: datetime
    ) -> tuple[int, str, float | None, bool, str]:
        """Resolve effective walking minutes without contacting routing providers."""
        static_minutes = max(0, int(self.walking_time))
        if not self.dynamic_walking_time:
            self._clear_walking_entity_issue()
            return (
                static_minutes,
                "static" if static_minutes > 0 else "disabled",
                None,
                False,
                "disabled",
            )

        entity_id = self.walking_time_entity
        if not entity_id:
            self._clear_walking_entity_issue()
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "not_configured",
            )

        state = self.hass.states.get(entity_id)
        if state is None:
            self._note_missing_walking_entity(entity_id)
            return (
                static_minutes,
                "static_fallback" if static_minutes > 0 else "disabled",
                None,
                True,
                "missing",
            )
        self._clear_walking_entity_issue()
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
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="gtfs_update_failed",
            ) from exc

        operators = list(self._services_by_operator)
        results: list[BODSLiveFeedResult] = await asyncio.gather(
            *(self.live_feed.async_get_operator(operator) for operator in operators)
        )

        vehicles = []
        route_errors: dict[str, str] = {}
        warnings: list[str] = []
        for operator, result in zip(operators, results, strict=True):
            operator_services = self._services_by_operator[operator]
            if result.payload is None:
                error = result.error or "unknown"
                for service in operator_services:
                    route_errors[service.key] = error
                continue

            try:
                parsed, _timestamp, parsed_warnings = await self.hass.async_add_executor_job(
                    parse_siri,
                    result.payload,
                    operator_services,
                )
                vehicles.extend(parsed)
                warnings.extend(parsed_warnings)
            except Exception as exc:
                for service in operator_services:
                    route_errors[service.key] = f"parse_error: {exc}"

        # Only a genuine HTTP 401 is an authentication failure. 403 may be a
        # BODS access/WAF response and 429 is rate limiting; neither should
        # force Home Assistant into a misleading reauthentication flow.
        if self.services and all(
            route_errors.get(service.key) == "authentication_failed"
            for service in self.services
        ):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="api_key_rejected",
            )

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

        self._log_live_health_transition(str(snapshot.get("health", "unknown")))

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
