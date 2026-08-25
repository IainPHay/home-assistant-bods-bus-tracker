"""BODS Bus Tracker integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_API_KEY,
    CONF_LEGACY_ENTITY_IDS,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_STOP,
)
from .coordinator import BODSBusCoordinator
from .gtfs import GTFSDownloadError

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BODSBusRuntimeData:
    """Runtime data for a BODS Bus Tracker account."""

    coordinators: dict[str, BODSBusCoordinator]


type BODSBusConfigEntry = ConfigEntry[BODSBusRuntimeData]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when stops/subentries are added, edited or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate v0.1/v0.2 one-stop entries to v0.3 account + stop subentry."""
    _LOGGER.debug(
        "Migrating BODS Bus Tracker entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version == 1:
        old_data = dict(entry.data)
        required = {
            CONF_API_KEY,
            CONF_REGION,
            CONF_STOP_ATCO,
            CONF_STOP_NAME,
            CONF_SERVICES,
        }
        if not required.issubset(old_data):
            _LOGGER.error("Cannot migrate BODS entry: required stop data is missing")
            return False

        stop_data = {
            CONF_REGION: old_data[CONF_REGION],
            CONF_STOP_ATCO: old_data[CONF_STOP_ATCO],
            CONF_STOP_NAME: old_data[CONF_STOP_NAME],
            CONF_SERVICES: list(old_data[CONF_SERVICES]),
            CONF_POLL_INTERVAL: int(
                entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            ),
            CONF_LEGACY_ENTITY_IDS: True,
        }
        subentry = ConfigSubentry(
            data=MappingProxyType(stop_data),
            subentry_type=SUBENTRY_TYPE_STOP,
            title=f"{old_data[CONF_STOP_NAME]} ({old_data[CONF_STOP_ATCO]})",
            unique_id=f"{old_data[CONF_REGION]}:{old_data[CONF_STOP_ATCO]}",
        )
        hass.config_entries.async_add_subentry(entry, subentry)

        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            if (DOMAIN, entry.entry_id) in device.identifiers:
                device_registry.async_update_device(
                    device.id,
                    new_config_subentry_id=subentry.subentry_id,
                )

        hass.config_entries.async_update_entry(
            entry,
            title="BODS Bus Tracker",
            data={CONF_API_KEY: old_data[CONF_API_KEY]},
            options={},
            unique_id=None,
            version=2,
            minor_version=0,
        )

    _LOGGER.debug(
        "BODS Bus Tracker migration complete at version %s.%s",
        entry.version,
        entry.minor_version,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BODSBusConfigEntry) -> bool:
    """Set up one BODS account and all configured stop subentries."""
    coordinators: dict[str, BODSBusCoordinator] = {}

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):
        coordinator = BODSBusCoordinator(hass, entry, subentry)
        try:
            await coordinator.async_prepare()
        except GTFSDownloadError as exc:
            raise ConfigEntryNotReady(
                f"Unable to prepare {subentry.title}: {exc}"
            ) from exc
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry.subentry_id] = coordinator

    entry.runtime_data = BODSBusRuntimeData(coordinators=coordinators)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BODSBusConfigEntry) -> bool:
    """Unload BODS Bus Tracker."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
