"""Shared entity helpers for BODS Bus Tracker."""

from __future__ import annotations

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN, VERSION


def stop_device_info(subentry: ConfigSubentry, identifier: str) -> DeviceInfo:
    """Return consistent device-registry metadata for a monitored bus stop."""
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=subentry.title,
        manufacturer="UK Department for Transport",
        model="BODS + GTFS bus ETA",
        sw_version=VERSION,
        configuration_url="https://data.bus-data.dft.gov.uk/",
        entry_type=DeviceEntryType.SERVICE,
    )
