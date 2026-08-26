"""Binary sensors for BODS Bus Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BODSBusConfigEntry
from .const import CONF_LEGACY_ENTITY_IDS, DOMAIN, SUBENTRY_TYPE_STOP, VERSION
from .coordinator import BODSBusCoordinator


class LeaveNowBinarySensor(CoordinatorEntity[BODSBusCoordinator], BinarySensorEntity):
    """Turn on when it is time to start walking to the selected stop."""

    _attr_has_entity_name = True
    _attr_name = "Leave now"
    _attr_icon = "mdi:walk"

    def __init__(
        self,
        coordinator: BODSBusCoordinator,
        entry: BODSBusConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._subentry = subentry
        if subentry.data.get(CONF_LEGACY_ENTITY_IDS):
            self._attr_unique_id = f"{entry.entry_id}_leave_now"
            self._device_identifier = entry.entry_id
        else:
            self._attr_unique_id = (
                f"{entry.entry_id}_{subentry.subentry_id}_leave_now"
            )
            self._device_identifier = f"{entry.entry_id}:{subentry.subentry_id}"

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

    @property
    def available(self) -> bool:
        data = self.coordinator.data.get("next_bus", {})
        return (
            super().available
            and bool(data.get("available"))
            and int(data.get("walking_minutes") or 0) > 0
            and bool(data.get("leave_by"))
        )

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        return bool(self.coordinator.data.get("next_bus", {}).get("leave_now"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data.get("next_bus", {})
        return {
            "walking_minutes": data.get("walking_minutes"),
            "leave_by": data.get("leave_by"),
            "leave_in_minutes": data.get("leave_in_minutes"),
            "expected": data.get("expected"),
            "route": data.get("route"),
            "destination": data.get("destination"),
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BODSBusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the per-stop Leave now binary sensor."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        coordinator = entry.runtime_data.coordinators.get(subentry.subentry_id)
        if coordinator is None:
            continue
        async_add_entities(
            [LeaveNowBinarySensor(coordinator, entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
