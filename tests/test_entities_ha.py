"""Entity and diagnostics tests for BODS Bus Tracker."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker import BODSBusRuntimeData
from custom_components.bods_bus_tracker.api import ServiceSpec
from custom_components.bods_bus_tracker.binary_sensor import (
    LeaveNowBinarySensor,
    async_setup_entry as async_setup_binary_sensors,
)
from custom_components.bods_bus_tracker.const import (
    CONF_API_KEY,
    CONF_CATCHABLE_MARGIN,
    CONF_DYNAMIC_WALKING_TIME,
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
)
from custom_components.bods_bus_tracker.diagnostics import (
    _strip_coordinates,
    async_get_config_entry_diagnostics,
)
from custom_components.bods_bus_tracker.entity import stop_device_info
from custom_components.bods_bus_tracker.sensor import (
    CatchableBusSensor,
    DiagnosticSensor,
    LastUpdateSensor,
    LeaveInSensor,
    NextBusDelaySensor,
    NextBusMinutesSensor,
    NextBusSensor,
    NextBusTimestampSensor,
    NextBusTimingSensor,
    ServiceSensor,
    _entities_for_stop,
    async_setup_entry as async_setup_sensors,
)


def _entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "super-secret"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_REGION: "north_east",
                    CONF_STOP_ATCO: "3100Z199842",
                    CONF_STOP_NAME: "The Fairway",
                    CONF_SERVICES: ["ANUM|X14", "ANUM|X18"],
                    CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                    CONF_WALKING_TIME: 5,
                    CONF_DYNAMIC_WALKING_TIME: False,
                    CONF_WALKING_TIME_ENTITY: "",
                    CONF_CATCHABLE_MARGIN: 2,
                    CONF_POLL_INTERVAL: 30,
                },
                subentry_id="fairway-stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (3100Z199842)",
                unique_id="north_east:3100Z199842",
            )
        ],
    )


def _coordinator(data: dict):
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = True
    coordinator.services = [
        ServiceSpec("ANUM", "X14", "Arriva Northumbria"),
        ServiceSpec("ANUM", "X18", "Arriva Northumbria"),
    ]
    return coordinator


def _sample_data() -> dict:
    now = datetime(2026, 9, 11, 13, 0, tzinfo=ZoneInfo("Europe/London"))
    return {
        "next_bus": {
            "available": True,
            "route": "X14",
            "minutes": 8,
            "scheduled": now.isoformat(),
            "expected": now.isoformat(),
            "delay_minutes": 2.5,
            "timing_status": "late",
            "leave_by": now.isoformat(),
            "leave_in_minutes": 3,
            "leave_now": False,
            "walking_minutes": 5,
            "destination": "Newcastle",
        },
        "services": {
            "ANUM|X14": {"minutes": 8, "route": "X14"},
            "ANUM|X18": {"minutes": 18, "route": "X18"},
        },
        "departures": [{"route": "X14"}],
        "arrivals": [],
        "next_departure": {"route": "X14"},
        "next_arrival": None,
        "stop_view": "departures",
        "terminus": {},
        "generated_at": now.isoformat(),
        "health": "ok",
        "live_vehicle_count": 5,
        "match_stats": {"matched": 4},
        "stop": {"atco": "3100Z199842", "latitude": 55.1, "longitude": -1.6},
        "catchable": {
            "status": "ok",
            "walking_minutes": 5,
            "margin_minutes": 2,
            "required_lead_minutes": 7,
            "departure": {
                "route": "X18",
                "destination": "Newcastle",
                "minutes": 18,
                "expected": now.isoformat(),
                "scheduled": now.isoformat(),
                "source": "scheduled",
            },
            "following_departure": {
                "route": "X14",
                "minutes": 28,
                "expected": now.isoformat(),
                "scheduled": now.isoformat(),
                "source": "scheduled",
            },
        },
    }


def test_stop_device_info_is_service_device() -> None:
    """A monitored stop is a logical service device, not pretend hardware."""
    entry = _entry()
    subentry = next(iter(entry.subentries.values()))

    info = stop_device_info(subentry, "identifier")

    assert info["identifiers"] == {(DOMAIN, "identifier")}
    assert info["name"] == "The Fairway (3100Z199842)"
    assert info["entry_type"] is DeviceEntryType.SERVICE


def test_entity_factory_and_values() -> None:
    """The stop entity set exposes stable values and Gold-quality metadata."""
    entry = _entry()
    subentry = next(iter(entry.subentries.values()))
    coordinator = _coordinator(_sample_data())

    entities = _entities_for_stop(entry, subentry, coordinator)

    next_bus = next(entity for entity in entities if isinstance(entity, NextBusSensor))
    assert next_bus.native_value == "X14"
    assert next_bus.extra_state_attributes["data_status"] == "ok"
    assert next_bus.extra_state_attributes["gtfs_matches"] == 4

    minutes = next(
        entity for entity in entities if isinstance(entity, NextBusMinutesSensor)
    )
    assert minutes.native_value == 8
    assert minutes.device_class == "duration"

    timestamps = [
        entity for entity in entities if isinstance(entity, NextBusTimestampSensor)
    ]
    assert len(timestamps) == 3
    assert all(entity.native_value is not None for entity in timestamps)

    delay = next(entity for entity in entities if isinstance(entity, NextBusDelaySensor))
    assert delay.available is True
    assert delay.native_value == 2.5
    assert delay.device_class == "duration"

    timing = next(
        entity for entity in entities if isinstance(entity, NextBusTimingSensor)
    )
    assert timing.native_value == "late"
    assert timing.options == ["early", "on_time", "late", "timetable"]
    assert timing.device_class == "enum"

    leave_in = next(entity for entity in entities if isinstance(entity, LeaveInSensor))
    assert leave_in.native_value == 3
    assert leave_in.extra_state_attributes["walking_minutes"] == 5

    catchable = next(
        entity for entity in entities if isinstance(entity, CatchableBusSensor)
    )
    assert catchable.available is True
    assert catchable.native_value == "X18"
    assert catchable.extra_state_attributes["required_lead_minutes"] == 7
    assert catchable.extra_state_attributes["following_departure"]["route"] == "X14"

    service_entities = [
        entity for entity in entities if isinstance(entity, ServiceSensor)
    ]
    assert {entity.native_value for entity in service_entities} == {8, 18}
    assert all(entity.device_class == "duration" for entity in service_entities)

    diagnostics = [
        entity for entity in entities if isinstance(entity, DiagnosticSensor)
    ]
    data_status = next(
        entity for entity in diagnostics if entity._attr_translation_key == "data_status"
    )
    assert data_status.native_value == "ok"
    assert data_status.entity_category is EntityCategory.DIAGNOSTIC

    counters = [
        entity
        for entity in diagnostics
        if entity._attr_translation_key in {"live_vehicles", "gtfs_matches"}
    ]
    assert all(
        entity._attr_entity_registry_enabled_default is False for entity in counters
    )

    last_update = next(
        entity for entity in entities if isinstance(entity, LastUpdateSensor)
    )
    assert last_update.native_value is not None
    assert last_update.entity_category is EntityCategory.DIAGNOSTIC

    assert all(entity.unique_id for entity in entities)
    assert all(entity.device_info["entry_type"] is DeviceEntryType.SERVICE for entity in entities)


def test_delay_sensor_unavailable_without_live_delay() -> None:
    """No live delay measurement is unavailable, not a fake string state."""
    entry = _entry()
    subentry = next(iter(entry.subentries.values()))
    data = _sample_data()
    data["next_bus"]["delay_minutes"] = None
    entity = NextBusDelaySensor(_coordinator(data), entry, subentry)

    assert entity.available is False
    assert entity.native_value is None


def test_leave_now_binary_sensor() -> None:
    """Leave now follows the coordinator's passenger-facing leave guidance."""
    entry = _entry()
    subentry = next(iter(entry.subentries.values()))
    data = _sample_data()
    coordinator = _coordinator(data)
    entity = LeaveNowBinarySensor(coordinator, entry, subentry)

    assert entity.available is True
    assert entity.is_on is False
    assert entity.extra_state_attributes["route"] == "X14"

    data["next_bus"]["leave_now"] = True
    assert entity.is_on is True

    data["next_bus"]["walking_minutes"] = 0
    assert entity.available is False
    assert entity.is_on is None


async def test_platform_setup_adds_stop_entities(hass) -> None:
    """Both platforms attach their entities to the stop config subentry."""
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = _coordinator(_sample_data())
    entry.runtime_data = BODSBusRuntimeData(
        coordinators={"fairway-stop": coordinator},
        live_feed=MagicMock(),
        timetables={},
    )

    sensor_add = MagicMock()
    await async_setup_sensors(hass, entry, sensor_add)
    assert sensor_add.call_count == 1
    sensor_entities = sensor_add.call_args.args[0]
    assert len(sensor_entities) == 14
    assert sensor_add.call_args.kwargs["config_subentry_id"] == "fairway-stop"

    binary_add = MagicMock()
    await async_setup_binary_sensors(hass, entry, binary_add)
    assert binary_add.call_count == 1
    assert isinstance(binary_add.call_args.args[0][0], LeaveNowBinarySensor)


def test_strip_coordinates_recursive() -> None:
    """Diagnostics remove vehicle coordinates recursively."""
    raw = {
        "latitude": 1,
        "nested": {
            "longitude": 2,
            "keep": [{"latitude": 3, "value": 4}],
        },
    }

    assert _strip_coordinates(raw) == {"nested": {"keep": [{"value": 4}]}}


async def test_diagnostics_redact_api_key_and_coordinates(hass) -> None:
    """Downloadable diagnostics contain useful state without secrets or GPS."""
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = _coordinator(_sample_data())
    entry.runtime_data = BODSBusRuntimeData(
        coordinators={"fairway-stop": coordinator},
        live_feed=MagicMock(),
        timetables={},
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry_data"][CONF_API_KEY] != "super-secret"
    exported = diagnostics["coordinators"]["fairway-stop"]
    assert "latitude" not in exported["stop"]
    assert "longitude" not in exported["stop"]
    assert exported["next_bus"]["route"] == "X14"
