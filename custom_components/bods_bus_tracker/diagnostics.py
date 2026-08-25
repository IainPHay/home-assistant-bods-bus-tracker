"""Diagnostics for BODS Bus Tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BODSBusConfigEntry
from .const import CONF_API_KEY

TO_REDACT = {CONF_API_KEY}


def _strip_coordinates(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_coordinates(item)
            for key, item in value.items()
            if key not in {"latitude", "longitude"}
        }
    if isinstance(value, list):
        return [_strip_coordinates(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BODSBusConfigEntry
) -> dict[str, Any]:
    """Return redacted account and per-stop diagnostics."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "subentries": {
            subentry.subentry_id: {
                "title": subentry.title,
                "type": subentry.subentry_type,
                "data": dict(subentry.data),
            }
            for subentry in entry.subentries.values()
        },
        "coordinators": {
            subentry_id: _strip_coordinates(coordinator.data)
            for subentry_id, coordinator in entry.runtime_data.coordinators.items()
        },
    }
