"""Sensor platform for BODS Bus Tracker."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import BODSBusConfigEntry
from .api import ServiceSpec
from .const import CONF_LEGACY_ENTITY_IDS, DOMAIN, SUBENTRY_TYPE_STOP, VERSION
from .coordinator import BODSBusCoordinator


class BODSBusBaseEntity(CoordinatorEntity[BODSBusCoordinator], SensorEntity):
    """Base BODS Bus Tracker sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
        unique_suffix: str,
        name: str,
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
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier)},
            name=self._subentry.title,
            manufacturer="UK Department for Transport",
            model="BODS + GTFS bus ETA",
            sw_version=VERSION,
            configuration_url="https://data.bus-data.dft.gov.uk/",
        )


class NextBusSensor(BODSBusBaseEntity):
    _attr_icon = "mdi:bus"

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus", "Next bus")

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
    _attr_icon = "mdi:bus-clock"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(
            coordinator, entry, subentry, "next_bus_minutes", "Next bus minutes"
        )

    @property
    def native_value(self):
        return self.coordinator.data.get("next_bus", {}).get("minutes")


class NextBusTimestampSensor(BODSBusBaseEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator,
        entry,
        subentry,
        field: str,
        suffix: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry, subentry, suffix, name)
        self._field = field
        self._attr_icon = icon

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.data.get("next_bus", {}).get(self._field)
        return datetime.fromisoformat(value) if value else None


class NextBusDelaySensor(BODSBusBaseEntity):
    _attr_icon = "mdi:clock-alert-outline"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus_delay", "Next bus delay")

    @property
    def native_value(self):
        return self.coordinator.data.get("next_bus", {}).get("delay_minutes")


class NextBusTimingSensor(BODSBusBaseEntity):
    """Friendly live timing state for the next bus."""

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(coordinator, entry, subentry, "next_bus_timing", "Next bus timing")

    @property
    def native_value(self):
        data = self.coordinator.data.get("next_bus", {})
        if not data.get("available"):
            return None
        return data.get("timing_status")

    @property
    def icon(self) -> str:
        value = self.native_value
        if value == "early":
            return "mdi:clock-fast"
        if value == "late":
            return "mdi:clock-alert-outline"
        if value == "on_time":
            return "mdi:clock-check-outline"
        return "mdi:calendar-clock"

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

    _attr_icon = "mdi:walk"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(coordinator, entry, subentry, "leave_in", "Leave in")

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
    _attr_icon = "mdi:bus-clock"
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
        name = (
            f"Next {service.route} ({service.operator_noc})"
            if duplicate_route
            else f"Next {service.route}"
        )
        super().__init__(coordinator, entry, subentry, suffix, name)
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
        self, coordinator, entry, subentry, key: str, name: str, icon: str
    ) -> None:
        super().__init__(coordinator, entry, subentry, key, name)
        self._key = key
        self._attr_icon = icon

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
    _attr_icon = "mdi:update"

    def __init__(self, coordinator, entry, subentry) -> None:
        super().__init__(coordinator, entry, subentry, "last_update", "Last update")

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
            "Next bus expected",
            "mdi:clock-check-outline",
        ),
        NextBusTimestampSensor(
            coordinator,
            entry,
            subentry,
            "scheduled",
            "next_bus_scheduled",
            "Next bus scheduled",
            "mdi:clock-outline",
        ),
        NextBusDelaySensor(coordinator, entry, subentry),
        NextBusTimingSensor(coordinator, entry, subentry),
        NextBusTimestampSensor(
            coordinator,
            entry,
            subentry,
            "leave_by",
            "leave_by",
            "Leave by",
            "mdi:walk",
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
                "Data status",
                "mdi:database-check-outline",
            ),
            LastUpdateSensor(coordinator, entry, subentry),
            DiagnosticSensor(
                coordinator,
                entry,
                subentry,
                "live_vehicles",
                "Live vehicles",
                "mdi:bus-multiple",
            ),
            DiagnosticSensor(
                coordinator,
                entry,
                subentry,
                "gtfs_matches",
                "GTFS matches",
                "mdi:link-variant",
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
