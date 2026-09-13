"""Coordinator behaviour tests for BODS Bus Tracker."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker.api import ServiceSpec, StopTime, Trip
from custom_components.bods_bus_tracker.const import (
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
    CONF_MAX_DYNAMIC_WALKING_TIME,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_VIEW,
    CONF_WALKING_TIME,
    CONF_WALKING_TIME_ENTITY,
    DOMAIN,
    STOP_VIEW_ARRIVALS,
    STOP_VIEW_DEPARTURES,
    SUBENTRY_TYPE_STOP,
)
from custom_components.bods_bus_tracker.coordinator import BODSBusCoordinator
from custom_components.bods_bus_tracker.live_feed import BODSLiveFeedResult

TZ = ZoneInfo("Europe/London")


def _entry(
    *,
    services: list[str] | None = None,
    stop_view: str = STOP_VIEW_DEPARTURES,
    walking: int = 5,
    dynamic: bool = False,
    walking_entity: str = "",
    max_dynamic: int = 120,
):
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
                    CONF_SERVICES: services or ["ANUM|X14"],
                    CONF_STOP_VIEW: stop_view,
                    CONF_WALKING_TIME: walking,
                    CONF_DYNAMIC_WALKING_TIME: dynamic,
                    CONF_WALKING_TIME_ENTITY: walking_entity,
                    CONF_MAX_DYNAMIC_WALKING_TIME: max_dynamic,
                    CONF_POLL_INTERVAL: 30,
                },
                subentry_id="stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (B)",
                unique_id="north_east:B",
            )
        ],
    )


def _trip(route: str = "X14", operator: str = "ANUM") -> Trip:
    return Trip(
        trip_id=f"{operator}-{route}",
        route=route,
        operator_noc=operator,
        operator_name="Operator",
        service_id="WK",
        headsign="Town",
        vehicle_journey_code="1",
        stops=[
            StopTime("A", 1, 36000, 36000, 55.0, -1.0, "Origin"),
            StopTime("B", 2, 36600, 36600, 55.1, -1.1, "The Fairway"),
        ],
    )


def _coordinator(
    hass,
    *,
    services: list[str] | None = None,
    stop_view: str = STOP_VIEW_DEPARTURES,
    walking: int = 5,
    dynamic: bool = False,
    walking_entity: str = "",
    max_dynamic: int = 120,
):
    entry = _entry(
        services=services,
        stop_view=stop_view,
        walking=walking,
        dynamic=dynamic,
        walking_entity=walking_entity,
        max_dynamic=max_dynamic,
    )
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))
    live_feed = MagicMock()
    live_feed.async_get_operator = AsyncMock()
    timetable = MagicMock()
    timetable.async_get = AsyncMock()
    coordinator = BODSBusCoordinator(hass, entry, subentry, live_feed, timetable)
    return coordinator, live_feed, timetable


async def test_shared_timetable_is_filtered_to_stop_services(hass) -> None:
    """A stop gets a cheap filtered view of the shared regional index."""
    coordinator, _live_feed, timetable = _coordinator(hass)
    timetable.async_get.return_value = (
        [_trip("X14", "ANUM"), _trip("O1", "OTHER")],
        {
            "index_generation": 1,
            "index_source": "memory",
            "index_prepare_seconds": 0.01,
            "shared_trip_count": 2,
        },
    )

    await coordinator.async_prepare()

    assert [trip.route for trip in coordinator._trips] == ["X14"]
    assert coordinator._gtfs_info["target_trip_count"] == 1
    assert coordinator._gtfs_info["index_initial_source"] == "memory"

    # A second sync at the same generation avoids rebuilding the stop view.
    await coordinator.async_prepare()
    assert timetable.async_get.await_count == 2


@pytest.mark.parametrize(
    ("static_minutes", "expected_mode"),
    [(5, "static"), (0, "disabled")],
)
async def test_static_walking_modes(
    hass, static_minutes: int, expected_mode: str
) -> None:
    """Static-only stops never depend on an external routing sensor."""
    coordinator, _, _ = _coordinator(hass, walking=static_minutes)
    values = coordinator._walking_guidance_values(datetime.now(TZ))

    assert values[0] == static_minutes
    assert values[1] == expected_mode
    assert values[4] == "disabled"


async def test_dynamic_walking_not_configured_uses_static_fallback(hass) -> None:
    """Dynamic mode without an entity safely falls back."""
    coordinator, _, _ = _coordinator(hass, dynamic=True, walking_entity="")
    values = coordinator._walking_guidance_values(datetime.now(TZ))

    assert values[0] == 5
    assert values[1] == "static_fallback"
    assert values[3] is True
    assert values[4] == "not_configured"


@pytest.mark.parametrize(
    ("state_value", "unit", "expected_status"),
    [
        ("unknown", "min", "unknown"),
        ("unavailable", "min", "unavailable"),
        ("not-a-number", "min", "invalid"),
        ("5", "widgets", "invalid"),
    ],
)
async def test_dynamic_walking_invalid_states_fall_back(
    hass, state_value: str, unit: str, expected_status: str
) -> None:
    """Temporary or malformed routing states retain static guidance."""
    coordinator, _, _ = _coordinator(
        hass,
        dynamic=True,
        walking_entity="sensor.walk",
    )
    now = datetime.now(TZ)
    fake = SimpleNamespace(
        state=state_value,
        attributes={"unit_of_measurement": unit},
        last_reported=now,
        last_updated=now,
    )

    with patch("homeassistant.core.StateMachine.get", return_value=fake):
        values = coordinator._walking_guidance_values(now)

    assert values[0] == 5
    assert values[1] == "static_fallback"
    assert values[3] is True
    assert values[4] == expected_status


async def test_dynamic_walking_stale_state_falls_back(hass) -> None:
    """A stale provider value is not used for passenger leave guidance."""
    coordinator, _, _ = _coordinator(
        hass,
        dynamic=True,
        walking_entity="sensor.walk",
    )
    now = datetime.now(TZ)
    old = now - timedelta(hours=1)
    fake = SimpleNamespace(
        state="8",
        attributes={"unit_of_measurement": "min"},
        last_reported=old,
        last_updated=old,
    )

    with patch("homeassistant.core.StateMachine.get", return_value=fake):
        values = coordinator._walking_guidance_values(now)

    assert values[1] == "static_fallback"
    assert values[4] == "stale"


async def test_dynamic_walking_valid_state_rounds_up(hass) -> None:
    """A current routed duration overrides the fallback and rounds up."""
    coordinator, _, _ = _coordinator(
        hass,
        dynamic=True,
        walking_entity="sensor.walk",
    )
    now = datetime.now(TZ)
    fake = SimpleNamespace(
        state="390",
        attributes={"unit_of_measurement": "s"},
        last_reported=now,
        last_updated=now,
    )

    with patch("homeassistant.core.StateMachine.get", return_value=fake):
        values = coordinator._walking_guidance_values(now)

    assert values == (7, "dynamic", 6.5, False, "ok")


async def test_dynamic_walking_uses_configured_maximum(hass) -> None:
    """The per-stop maximum replaces the old fixed 120-minute ceiling."""
    now = datetime.now(TZ)
    fake = SimpleNamespace(
        state="407.266666666667",
        attributes={"unit_of_measurement": "min"},
        last_reported=now,
        last_updated=now,
    )

    default_coordinator, _, _ = _coordinator(
        hass,
        dynamic=True,
        walking=0,
        walking_entity="sensor.walk",
    )
    with patch("homeassistant.core.StateMachine.get", return_value=fake):
        default_values = default_coordinator._walking_guidance_values(now)

    assert default_values == (0, "disabled", None, True, "invalid")

    expanded_coordinator, _, _ = _coordinator(
        hass,
        dynamic=True,
        walking=0,
        walking_entity="sensor.walk",
        max_dynamic=500,
    )
    with patch("homeassistant.core.StateMachine.get", return_value=fake):
        expanded_values = expanded_coordinator._walking_guidance_values(now)

    assert expanded_values == (408, "dynamic", 407.266666666667, False, "ok")


def test_live_health_transition_logging(hass, caplog) -> None:
    """Live-data availability logs only on meaningful state transitions."""
    coordinator, _, _ = _coordinator(hass)
    caplog.set_level(logging.INFO)

    coordinator._log_live_health_transition("scheduled_only")
    coordinator._log_live_health_transition("scheduled_only")
    coordinator._log_live_health_transition("degraded")
    coordinator._log_live_health_transition("ok")

    assert caplog.text.count("using timetable data") == 1
    assert caplog.text.count("is degraded") == 1
    assert caplog.text.count("available again") == 1


async def test_all_401_results_trigger_reauth(hass) -> None:
    """Only a genuine all-service 401 result raises ConfigEntryAuthFailed."""
    coordinator, live_feed, timetable = _coordinator(hass)
    timetable.async_get.return_value = (
        [_trip()],
        {
            "index_generation": 1,
            "index_source": "memory",
            "index_prepare_seconds": 0.0,
        },
    )
    live_feed.async_get_operator.return_value = BODSLiveFeedResult(
        payload=None,
        error="authentication_failed",
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize("error", ["access_forbidden", "rate_limited", "timeout"])
async def test_non_401_live_failures_use_timetable(hass, error: str) -> None:
    """403/429/network failures become scheduled-only instead of reauth."""
    coordinator, live_feed, timetable = _coordinator(hass)
    timetable.async_get.return_value = (
        [_trip()],
        {
            "index_generation": 1,
            "index_source": "memory",
            "index_prepare_seconds": 0.0,
        },
    )
    live_feed.async_get_operator.return_value = BODSLiveFeedResult(
        payload=None,
        error=error,
    )

    snapshot = await coordinator._async_update_data()

    assert snapshot["health"] == "scheduled_only"
    assert snapshot["api_errors"]["ANUM|X14"] == error


async def test_parse_failure_is_contained_per_service(hass) -> None:
    """Malformed SIRI does not crash the timetable fallback."""
    coordinator, live_feed, timetable = _coordinator(hass)
    timetable.async_get.return_value = (
        [_trip()],
        {
            "index_generation": 1,
            "index_source": "memory",
            "index_prepare_seconds": 0.0,
        },
    )
    live_feed.async_get_operator.return_value = BODSLiveFeedResult(payload=b"bad")

    with patch(
        "custom_components.bods_bus_tracker.coordinator.parse_siri",
        side_effect=ValueError("bad xml"),
    ):
        snapshot = await coordinator._async_update_data()

    assert snapshot["health"] == "scheduled_only"
    assert snapshot["api_errors"]["ANUM|X14"].startswith("parse_error:")


async def test_arrivals_mode_skips_walking_guidance(hass) -> None:
    """Arrival-only stops never expose leave guidance."""
    coordinator, live_feed, timetable = _coordinator(
        hass,
        stop_view=STOP_VIEW_ARRIVALS,
    )
    timetable.async_get.return_value = (
        [_trip()],
        {
            "index_generation": 1,
            "index_source": "memory",
            "index_prepare_seconds": 0.0,
        },
    )
    live_feed.async_get_operator.return_value = BODSLiveFeedResult(payload=None, error="timeout")

    snapshot = await coordinator._async_update_data()

    assert "walking_mode" not in snapshot["next_bus"]
