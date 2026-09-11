"""Targeted Home Assistant quality-scale edge tests."""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker import (
    _async_reload_entry,
    _cleanup_orphan_walking_issues,
    async_remove_config_entry_device,
    async_setup_entry,
)
from custom_components.bods_bus_tracker.api import ServiceSpec, StopTime, Trip
from custom_components.bods_bus_tracker.const import (
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
    CONF_LEGACY_ENTITY_IDS,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_VIEW,
    CONF_WALKING_TIME,
    CONF_WALKING_TIME_ENTITY,
    DOMAIN,
    STOP_VIEW_DEPARTURES,
    SUBENTRY_TYPE_STOP,
    WALKING_ISSUE_PREFIX,
)
from custom_components.bods_bus_tracker.gtfs import GTFSDownloadError
from custom_components.bods_bus_tracker.sensor import (
    BODSBusBaseEntity,
    DiagnosticSensor,
    NextBusTimingSensor,
    ServiceSensor,
    async_setup_entry as async_setup_sensors,
)
from custom_components.bods_bus_tracker.stop_view import (
    _enrich_row,
    _stop_profile,
    _trip_role,
)
from custom_components.bods_bus_tracker.walking import apply_walking_guidance

TZ = ZoneInfo("Europe/London")


def _trip(*, target: bool = True, origin: bool = False) -> Trip:
    if not target:
        stops = [
            StopTime("A", 1, 36000, 36000, 55.0, -1.0, "A"),
            StopTime("C", 2, 36600, 36600, 55.1, -1.1, "C"),
        ]
    elif origin:
        stops = [
            StopTime("B", 1, 36000, 36000, 55.0, -1.0, "B"),
            StopTime("C", 2, 36600, 36600, 55.1, -1.1, "C"),
        ]
    else:
        stops = [
            StopTime("A", 1, 36000, 36000, 55.0, -1.0, "A"),
            StopTime("B", 2, 36600, 36600, 55.1, -1.1, "B"),
        ]
    return Trip(
        trip_id="t",
        route="X14",
        operator_noc="ANUM",
        operator_name="Arriva",
        service_id="WK",
        headsign="Town",
        vehicle_journey_code="1",
        stops=stops,
    )


def _entry(*, legacy: bool = False) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_REGION: "north_east",
                    CONF_STOP_ATCO: "B",
                    CONF_STOP_NAME: "The Fairway",
                    CONF_SERVICES: ["ANUM|X14"],
                    CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                    CONF_WALKING_TIME: 5,
                    CONF_DYNAMIC_WALKING_TIME: False,
                    CONF_WALKING_TIME_ENTITY: "",
                    CONF_POLL_INTERVAL: 30,
                    CONF_LEGACY_ENTITY_IDS: legacy,
                },
                subentry_id="stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (B)",
                unique_id="north_east:B",
            )
        ],
    )


def _coordinator(data: dict | None = None):
    coordinator = MagicMock()
    coordinator.data = data or {}
    coordinator.last_update_success = True
    coordinator.services = [ServiceSpec("ANUM", "X14", "Arriva")]
    return coordinator


def test_stop_view_edge_helpers() -> None:
    """Missing stops/trips and an origin-only profile are handled conservatively."""
    missing = _trip(target=False)
    origin = _trip(origin=True)

    assert _trip_role(missing, "B") is None
    assert _stop_profile([origin], "B")["profile"] == "origin"

    row = {
        "stop_role": "origin",
        "realtime": False,
        "latitude": None,
        "longitude": None,
    }
    no_trip = _enrich_row(row, None, "B")
    assert no_trip["origin"] is None
    assert no_trip["at_stop"] is False

    missing_target = _enrich_row(row, missing, "B")
    assert missing_target["origin"] == "A"
    assert missing_target["previous_stop"] is None
    assert missing_target["distance_to_stop_m"] is None


def test_walking_guidance_invalid_snapshot_and_expected_values() -> None:
    """Malformed or incomplete dashboard data never crashes leave guidance."""
    now = datetime(2026, 9, 11, 12, 0, tzinfo=TZ)

    raw = {"next_bus": "not-a-dict"}
    assert apply_walking_guidance(raw, now, 5) is raw

    missing_expected = {"next_bus": {"available": True}}
    result = apply_walking_guidance(missing_expected, now, 5)
    assert result["next_bus"]["leave_by"] is None

    bad_expected = {"next_bus": {"available": True, "expected": "not-a-date"}}
    result = apply_walking_guidance(bad_expected, now, 5)
    assert result["next_bus"]["leave_by"] is None

    naive_expected = {
        "next_bus": {
            "available": True,
            "expected": "2026-09-11T12:30:00",
        }
    }
    result = apply_walking_guidance(naive_expected, now, 5)
    assert result["next_bus"]["leave_by"].endswith("+01:00")


async def test_reload_listener_calls_config_entry_reload(hass) -> None:
    """Changing stop data requests a normal config-entry reload."""
    entry = _entry()
    with patch.object(
        hass.config_entries,
        "async_reload",
        new=AsyncMock(return_value=True),
    ) as reload_entry:
        await _async_reload_entry(hass, entry)

    reload_entry.assert_awaited_once_with(entry.entry_id)


def test_orphan_repair_cleanup(hass) -> None:
    """Repair issues for removed stop subentries are removed at setup."""
    entry = _entry()
    valid = f"{WALKING_ISSUE_PREFIX}stop"
    orphan = f"{WALKING_ISSUE_PREFIX}old-stop"

    for issue_id in (valid, orphan):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="walking_time_entity_missing",
            translation_placeholders={"entity_id": "sensor.x", "stop": "Stop"},
        )

    _cleanup_orphan_walking_issues(hass, entry)

    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, valid) is not None
    assert registry.async_get_issue(DOMAIN, orphan) is None


async def test_setup_gtfs_failure_requests_retry(hass) -> None:
    """An unusable timetable at startup becomes ConfigEntryNotReady."""
    entry = _entry()
    entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.async_prepare = AsyncMock(side_effect=GTFSDownloadError("offline"))

    with (
        patch(
            "custom_components.bods_bus_tracker.BODSBusCoordinator",
            return_value=coordinator,
        ),
        patch(
            "custom_components.bods_bus_tracker.SharedGTFSRegionIndex",
            return_value=MagicMock(),
        ),
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_legacy_stale_device_identifier_is_retained(hass) -> None:
    """Legacy migrated device identifiers are recognised as current."""
    entry = _entry(legacy=True)
    entry.add_to_hass(hass)
    device = MagicMock()
    device.identifiers = {(DOMAIN, entry.entry_id)}

    assert await async_remove_config_entry_device(hass, entry, device) is False


def test_sensor_legacy_ids_and_unavailable_timing() -> None:
    """Migrated sensors keep their old IDs and unavailable timing is None."""
    entry = _entry(legacy=True)
    subentry = next(iter(entry.subentries.values()))
    coordinator = _coordinator({"next_bus": {"available": False}})

    base = BODSBusBaseEntity(
        coordinator,
        entry,
        subentry,
        "test",
        "next_bus",
    )
    assert base.unique_id == f"{entry.entry_id}_test"
    assert base.device_info["identifiers"] == {(DOMAIN, entry.entry_id)}

    timing = NextBusTimingSensor(coordinator, entry, subentry)
    assert timing.native_value is None
    assert timing.extra_state_attributes == {
        "raw_delay_minutes": None,
        "effective_delay_minutes": None,
        "stop_role": None,
        "prediction_clamped": None,
    }


def test_service_and_diagnostic_sensor_branches() -> None:
    """Per-service attributes and each diagnostic value branch are exposed."""
    entry = _entry()
    subentry = next(iter(entry.subentries.values()))
    data = {
        "services": {"ANUM|X14": {"minutes": 4, "destination": "Town"}},
        "health": "degraded",
        "live_vehicle_count": 8,
        "match_stats": {"matched": 7},
    }
    coordinator = _coordinator(data)

    service = ServiceSensor(
        coordinator,
        entry,
        subentry,
        ServiceSpec("ANUM", "X14", "Arriva"),
        duplicate_route=False,
    )
    assert service.extra_state_attributes["destination"] == "Town"

    live = DiagnosticSensor(coordinator, entry, subentry, "live_vehicles")
    matches = DiagnosticSensor(coordinator, entry, subentry, "gtfs_matches")
    unknown = DiagnosticSensor(coordinator, entry, subentry, "other")
    assert live.native_value == 8
    assert matches.native_value == 7
    assert unknown.native_value is None


async def test_sensor_platform_skips_subentry_without_coordinator(hass) -> None:
    """A removed/reloading stop cannot create orphan entities."""
    entry = _entry()
    entry.add_to_hass(hass)
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinators = {}

    add_entities = MagicMock()
    await async_setup_sensors(hass, entry, add_entities)
    add_entities.assert_not_called()
