"""Home Assistant-native bus-stop subentry flow tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.config_entries import ConfigSubentryData, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker.api import ServiceChoice, StopChoice, StopDiscovery
from custom_components.bods_bus_tracker.const import (
    AUTO_REGION,
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
    CONF_MAX_DYNAMIC_WALKING_TIME,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_SEARCH,
    CONF_STOP_SELECTION,
    CONF_STOP_VIEW,
    CONF_WALKING_TIME,
    CONF_WALKING_TIME_ENTITY,
    DOMAIN,
    STOP_VIEW_BOTH,
    STOP_VIEW_DEPARTURES,
    SUBENTRY_TYPE_STOP,
)


STOP = StopChoice(
    stop_id="3100Z199842",
    stop_code="nldawjgp",
    stop_name="The Fairway",
    lat=55.1524,
    lon=-1.6880,
)
STOP_2 = StopChoice(
    stop_id="4100008HAYQS",
    stop_code="",
    stop_name="Haymarket Bus Station",
    lat=54.9778,
    lon=-1.6136,
)
DISCOVERY = StopDiscovery(
    stop_id=STOP.stop_id,
    stop_name=STOP.stop_name,
    services=(
        ServiceChoice(
            operator_noc="ANUM",
            route="X14",
            operator_name="Arriva Northumbria",
            headsigns=("Newcastle",),
        ),
        ServiceChoice(
            operator_noc="ANUM",
            route="X18",
            operator_name="Arriva Northumbria",
            headsigns=("Newcastle",),
        ),
    ),
)


def _entry(*, with_stop: bool = False) -> MockConfigEntry:
    """Create the shared BODS account test entry."""
    subentries = None
    if with_stop:
        subentries = [
            ConfigSubentryData(
                data={
                    CONF_REGION: "north_east",
                    CONF_STOP_ATCO: STOP.stop_id,
                    CONF_STOP_NAME: STOP.stop_name,
                    CONF_SERVICES: ["ANUM|X14"],
                    CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                    CONF_WALKING_TIME: 5,
                    CONF_DYNAMIC_WALKING_TIME: False,
                    CONF_WALKING_TIME_ENTITY: "",
                    CONF_POLL_INTERVAL: 30,
                },
                subentry_id="fairway-stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title=f"{STOP.stop_name} ({STOP.stop_id})",
                unique_id=f"north_east:{STOP.stop_id}",
            )
        ]
    return MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "test-key"},
        version=2,
        subentries_data=subentries,
    )


async def _start_stop_flow(hass, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )


async def _to_services_form(hass, entry: MockConfigEntry):
    result = await _start_stop_flow(hass, entry)
    assert result["step_id"] == "user"
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP,),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: "The Fairway"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "services"
    return result


async def test_add_stop_success(hass) -> None:
    """A searched stop can be added entirely through the UI."""
    entry = _entry()
    result = await _to_services_form(hass, entry)

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERVICES: ["ANUM|X14", "ANUM|X18"],
                CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                CONF_WALKING_TIME: 7,
                CONF_DYNAMIC_WALKING_TIME: False,
                CONF_POLL_INTERVAL: 30,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "The Fairway (3100Z199842)"
    assert result2["unique_id"] == "north_east:3100Z199842"
    assert result2["data"][CONF_SERVICES] == ["ANUM|X14", "ANUM|X18"]
    assert result2["data"][CONF_WALKING_TIME] == 7


async def test_add_stop_requires_service(hass) -> None:
    """At least one service must be selected."""
    entry = _entry()
    result = await _to_services_form(hass, entry)

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_SERVICES: [],
            CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
            CONF_WALKING_TIME: 5,
            CONF_DYNAMIC_WALKING_TIME: False,
            CONF_POLL_INTERVAL: 30,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_SERVICES: "select_service"}


async def test_dynamic_walking_requires_sensor(hass) -> None:
    """Routed walking cannot be enabled without a duration sensor."""
    entry = _entry()
    result = await _to_services_form(hass, entry)

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_SERVICES: ["ANUM|X14"],
            CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
            CONF_WALKING_TIME: 5,
            CONF_DYNAMIC_WALKING_TIME: True,
            CONF_POLL_INTERVAL: 30,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        CONF_WALKING_TIME_ENTITY: "walking_time_entity_required"
    }


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "invalid_auth"), (403, "access_forbidden"), (429, "rate_limited")],
)
async def test_selected_service_http_errors(hass, status: int, expected: str) -> None:
    """Service validation exposes auth/access/throttling distinctly."""
    entry = _entry()
    result = await _to_services_form(hass, entry)

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
        new=AsyncMock(side_effect=ClientResponseError(None, (), status=status)),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERVICES: ["ANUM|X14"],
                CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                CONF_WALKING_TIME: 5,
                CONF_DYNAMIC_WALKING_TIME: False,
                CONF_POLL_INTERVAL: 30,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected}


async def test_stop_search_requires_value(hass) -> None:
    """Empty stop searches are rejected without touching GTFS."""
    entry = _entry()
    result = await _start_stop_flow(hass, entry)

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_REGION: "north_east", CONF_STOP_SEARCH: "  "},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_STOP_SEARCH: "stop_search_required"}


async def test_auto_region_requires_exact_code(hass) -> None:
    """Automatic region detection is limited to exact stop codes."""
    entry = _entry()
    result = await _start_stop_flow(hass, entry)

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_REGION: AUTO_REGION, CONF_STOP_SEARCH: "The Fairway"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_STOP_SEARCH: "auto_requires_stop_code"}


async def test_auto_region_exact_code(hass) -> None:
    """An exact stop code can auto-detect its BODS region."""
    entry = _entry()
    result = await _start_stop_flow(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow._async_auto_detect_stop",
            new=AsyncMock(return_value=("north_east", STOP)),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: AUTO_REGION, CONF_STOP_SEARCH: STOP.stop_id},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "services"


async def test_multiple_stop_results_show_selection(hass) -> None:
    """Ambiguous name search asks the user to choose the boarding point."""
    entry = _entry()
    result = await _start_stop_flow(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP, STOP_2),
        ),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: "Bus"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "stop_select"

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
    ):
        result3 = await hass.config_entries.subentries.async_configure(
            result2["flow_id"],
            {CONF_STOP_SELECTION: STOP.stop_id},
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "services"


async def test_invalid_stop_selection_stays_on_form(hass) -> None:
    """A stale/invalid selection value cannot progress the flow."""
    entry = _entry()
    result = await _start_stop_flow(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP, STOP_2),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: "Bus"},
        )

    # Home Assistant's select schema rejects values that are not one of the
    # presented options before the integration handler is called.
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STOP_SELECTION: "not-a-stop"},
        )


async def test_duplicate_stop_aborts(hass) -> None:
    """The same physical stop cannot be configured twice."""
    entry = _entry(with_stop=True)
    result = await _to_services_form(hass, entry)

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
        new=AsyncMock(return_value=None),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERVICES: ["ANUM|X14"],
                CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                CONF_WALKING_TIME: 5,
                CONF_DYNAMIC_WALKING_TIME: False,
                CONF_POLL_INTERVAL: 30,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_stop(hass) -> None:
    """An existing stop can be reconfigured through the native subentry flow."""
    entry = _entry(with_stop=True)
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/gtfs.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_STOP),
            context={
                "source": SOURCE_RECONFIGURE,
                "subentry_id": subentry.subentry_id,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERVICES: ["ANUM|X14", "ANUM|X18"],
                CONF_STOP_VIEW: STOP_VIEW_BOTH,
                CONF_WALKING_TIME: 6,
                CONF_DYNAMIC_WALKING_TIME: True,
                CONF_WALKING_TIME_ENTITY: "sensor.walk_to_fairway",
                CONF_MAX_DYNAMIC_WALKING_TIME: 480,
                CONF_POLL_INTERVAL: 60,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    updated = entry.subentries[subentry.subentry_id]
    assert updated.data[CONF_STOP_VIEW] == STOP_VIEW_BOTH
    assert updated.data[CONF_WALKING_TIME_ENTITY] == "sensor.walk_to_fairway"
    assert updated.data[CONF_MAX_DYNAMIC_WALKING_TIME] == 480
    assert updated.data[CONF_POLL_INTERVAL] == 60
