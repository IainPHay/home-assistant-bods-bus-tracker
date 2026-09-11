"""Sensor platform for BODS Bus Tracker."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory, MATCH_ALL, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import BODSBusConfigEntry
from .api import ServiceSpec
from .const import CONF_LEGACY_ENTITY_IDS, SUBENTRY_TYPE_STOP
from .coordinator import BODSBusCoordinator
from .entity import stop_device_info

PARALLEL_UPDATES = 0


class BODSBusBaseEntity(CoordinatorEntity[BODSBusCoordinator], SensorEntity):
    """Base BODS Bus Tracker sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
        unique_suffix: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._subentry = subentry
        if subentry.data.get(CONF_LEGACY_ENTITY_IDS):
            self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
            self._device_identifier = entry.entry_id
        else:
            self._attr_unique_id = (
                f"{entry.entry_id}_{subentry.subentry_id}_{unique_suffix}"
            )
            self._device_identifier = f"{entry.entry_id}:{subentry.subentry_id}"
        self._attr_translation_key = translation_key

    @property
    def device_info(self):
        """Return the monitored stop as a service device."""
        return stop_device_info(self._subentry, self._device_identifier)


class NextBusSensor(BODSBusBaseEntity):
    # The rich rolling timetable/vehicle attributes are intentionally available live
    # for dashboards and automations, but can exceed Recorder's 16 KiB attribute
    # limit at busy stops. They are transient data and are therefore not persisted.
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus", "next_bus")

    @property
    def native_value(self):
        data = self.coordinator.data.get("next_bus", {})
        return data.get("route") if data.get("available") else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.coordinator.data
        data = dict(snapshot.get("next_bus", {}))
        data["departures"] = snapshot.get("departures", [])
        data["arrivals"] = snapshot.get("arrivals", [])
        data["next_departure"] = snapshot.get("next_departure")
        data["next_arrival"] = snapshot.get("next_arrival")
        data["stop_view"] = snapshot.get("stop_view")
        data["terminus"] = snapshot.get("terminus")
        data["tracker_updated"] = snapshot.get("generated_at")
        data["data_status"] = snapshot.get("health")
        data["live_vehicle_count"] = snapshot.get("live_vehicle_count")
        data["gtfs_matches"] = snapshot.get("match_stats", {}).get("matched")
        data["stop"] = snapshot.get("stop")
        return data


class NextBusMinutesSensor(BODSBusBaseEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(
            coordinator, entry, subentry, "next_bus_minutes", "next_bus_minutes"
        )

    @property
    def native_value(self):
        return self.coordinator.data.get("next_bus", {}).get("minutes")


class NextBusTimestampSensor(BODSBusBaseEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
        field: str,
        suffix: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator, entry, subentry, suffix, translation_key)
        self._field = field

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get("next_bus", {}).get(self._field)
        return datetime.fromisoformat(value) if value else None


class NextBusDelaySensor(BODSBusBaseEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus_delay", "next_bus_delay")

    @property
    def available(self) -> bool:
        """Only expose a numeric delay while a live delay estimate exists."""
        return (
            super().available
            and self.coordinator.data.get("next_bus", {}).get("delay_minutes") is not None
        )

    @property
    def native_value(self):
        return self.coordinator.data.get("next_bus", {}).get("delay_minutes")


class NextBusTimingSensor(BODSBusBaseEntity):
    """Friendly live timing state for the next bus."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["early", "on_time", "late", "timetable"]

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus_timing", "next_bus_timing")

    @property
    def native_value(self):
        data = self.coordinator.data.get("next_bus", {})
        if not data.get("available"):
            return None
        return data.get("timing_status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data.get("next_bus", {})
        return {
            "raw_delay_minutes": data.get("raw_delay_minutes"),
            "effective_delay_minutes": data.get("delay_minutes"),
            "stop_role": data.get("stop_role"),
            "prediction_clamped": data.get("prediction_clamped"),
        }


class LeaveInSensor(BODSBusBaseEntity):
    """Minutes remaining until the user should leave for the next bus."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator, entry, subentry, "leave_in", "leave_in")

    @property
    def native_value(self):
        return self.coordinator.data.get("next_bus", {}).get("leave_in_minutes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data.get("next_bus", {})
        return {
            "walking_minutes": data.get("walking_minutes"),
            "leave_by": data.get("leave_by"),
            "expected": data.get("expected"),
            "route": data.get("route"),
        }


class ServiceSensor(BODSBusBaseEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
        service: ServiceSpec,
        duplicate_route: bool,
    ) -> None:
        suffix = f"next_{slugify(service.operator_noc)}_{slugify(service.route)}"
        translation_key = (
            "next_service_operator" if duplicate_route else "next_service"
        )
        super().__init__(coordinator, entry, subentry, suffix, translation_key)
        self._attr_translation_placeholders = {
            "route": service.route,
            "operator": service.operator_noc,
        }
        self._service = service

    @property
    def native_value(self):
        return self.coordinator.data.get("services", {}).get(self._service.key, {}).get(
            "minutes"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(
            self.coordinator.data.get("services", {}).get(self._service.key, {})
        )


class DiagnosticSensor(BODSBusBaseEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
        key: str,
        *,
        enabled_default: bool = True,
    ) -> None:
        super().__init__(coordinator, entry, subentry, key, key)
        self._key = key
        self._attr_entity_registry_enabled_default = enabled_default
        if key == "data_status":
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = ["ok", "degraded", "scheduled_only"]

    @property
    def native_value(self):
        data = self.coordinator.data
        if self._key == "data_status":
            return data.get("health")
        if self._key == "live_vehicles":
            return data.get("live_vehicle_count")
        if self._key == "gtfs_matches":
            return data.get("match_stats", {}).get("matched")
        return None


class LastUpdateSensor(BODSBusBaseEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator, entry, subentry, "last_update", "last_update")

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get("generated_at")
        return datetime.fromisoformat(value) if value else None


def _entities_for_stop(
    entry: BODSBusConfigEntry,
    subentry: ConfigSubentry,
    coordinator: BODSBusCoordinator,
) -> list[SensorEntity]:
    entities: list[SensorEntity] = [
        NextBusSensor(coordinator, entry, subentry),
        NextBusMinutesSensor(coordinator, entry, subentry),
        NextBusTimestampSensor(
            coordinator,
            entry,
            subentry,
            "expected",
            "next_bus_expected",
            "next_bus_expected",
        ),
        NextBusTimestampSensor(
            coordinator,
            entry,
            subentry,
            "scheduled",
            "next_bus_scheduled",
            "next_bus_scheduled",
        ),
        NextBusDelaySensor(coordinator, entry, subentry),
        NextBusTimingSensor(coordinator, entry, subentry),
        NextBusTimestampSensor(
            coordinator,
            entry,
            subentry,
            "leave_by",
            "leave_by",
            "leave_by",
        ),
        LeaveInSensor(coordinator, entry, subentry),
    ]

    route_counts: dict[str, int] = {}
    for service in coordinator.services:
        route_counts[service.route] = route_counts.get(service.route, 0) + 1
    entities.extend(
        ServiceSensor(
            coordinator,
            entry,
            subentry,
            service,
            duplicate_route=route_counts[service.route] > 1,
        )
        for service in coordinator.services
    )
    entities.extend(
        [
            DiagnosticSensor(
                coordinator,
                entry,
                subentry,
                "data_status",
            ),
            LastUpdateSensor(coordinator, entry, subentry),
            DiagnosticSensor(
                coordinator,
                entry,
                subentry,
                "live_vehicles",
                enabled_default=False,
            ),
            DiagnosticSensor(
                coordinator,
                entry,
                subentry,
                "gtfs_matches",
                enabled_default=False,
            ),
        ]
    )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BODSBusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for every configured stop subentry."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        coordinator = entry.runtime_data.coordinators.get(subentry.subentry_id)
        if coordinator is None:
            continue
        async_add_entities(
            _entities_for_stop(entry, subentry, coordinator),
            config_subentry_id=subentry.subentry_id,
        )
