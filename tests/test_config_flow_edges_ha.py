"""Additional config-flow branch coverage for BODS Bus Tracker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant.config_entries import ConfigSubentryData, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker.api import ServiceChoice, StopChoice, StopDiscovery
from custom_components.bods_bus_tracker.config_flow import (
    BODSBusTrackerConfigFlow,
    BODSStopSubentryFlow,
    _async_auto_detect_stop,
    _async_validate_api_key,
    _async_validate_api_key_generic,
    _config_error_from_http_status,
    _distance_sq,
    _region_options,
    _region_search_order,
    _service_options,
    _stop_view_options,
)
from custom_components.bods_bus_tracker.const import (
    AUTO_REGION,
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
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
    STOP_VIEW_DEPARTURES,
    SUBENTRY_TYPE_STOP,
)
from custom_components.bods_bus_tracker.gtfs import GTFSDownloadError


STOP = StopChoice(
    stop_id="3100Z199842",
    stop_code="nldawjgp",
    stop_name="The Fairway",
    lat=55.15,
    lon=-1.68,
)
EMPTY_DISCOVERY = StopDiscovery(
    stop_id=STOP.stop_id,
    stop_name=STOP.stop_name,
    services=(),
)
DISCOVERY = StopDiscovery(
    stop_id=STOP.stop_id,
    stop_name=STOP.stop_name,
    services=(
        ServiceChoice(
            operator_noc="ANUM",
            route="X14",
            operator_name="Arriva",
            headsigns=("Newcastle",),
        ),
    ),
)


class FakeResponse:
    def __init__(self, status: int = 200, payload: bytes = b"ok") -> None:
        self.status = status
        self.payload = payload
        self.read_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(None, (), status=self.status)

    async def read(self) -> bytes:
        self.read_called = True
        return self.payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.urls: list[str] = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.response


def _entry(*, walking_entity: str = "") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_REGION: "north_east",
                    CONF_STOP_ATCO: STOP.stop_id,
                    CONF_STOP_NAME: STOP.stop_name,
                    CONF_SERVICES: ["ANUM|X14"],
                    CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                    CONF_WALKING_TIME: 5,
                    CONF_DYNAMIC_WALKING_TIME: bool(walking_entity),
                    CONF_WALKING_TIME_ENTITY: walking_entity,
                    CONF_POLL_INTERVAL: 30,
                },
                subentry_id="stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (3100Z199842)",
                unique_id=f"north_east:{STOP.stop_id}",
            )
        ],
    )


def test_config_http_mapping_and_select_options(hass) -> None:
    """Small flow helpers expose the intended UI choices and errors."""
    assert _config_error_from_http_status(401) == "invalid_auth"
    assert _config_error_from_http_status(403) == "access_forbidden"
    assert _config_error_from_http_status(429) == "rate_limited"
    assert _config_error_from_http_status(500) == "cannot_connect"

    assert _distance_sq(55.0, -1.0, 55.0, -1.0) == 0
    assert _region_options()[0]["value"] == AUTO_REGION
    assert len(_region_search_order(hass)) >= 1
    assert {option["value"] for option in _stop_view_options()} == {
        "departures",
        "arrivals",
        "both",
    }
    assert _service_options(DISCOVERY)[0]["value"] == "ANUM|X14"


async def test_direct_api_key_validators_build_filtered_urls(hass) -> None:
    """Setup-time validation requests are deliberately small and filtered."""
    generic_response = FakeResponse()
    generic_session = FakeSession(generic_response)
    with patch(
        "custom_components.bods_bus_tracker.config_flow.async_get_clientsession",
        return_value=generic_session,
    ):
        await _async_validate_api_key_generic(hass, "abc")

    assert "/api/v1/dataset/" in generic_session.urls[0]
    assert "api_key=abc" in generic_session.urls[0]
    assert "limit=1" in generic_session.urls[0]
    assert generic_response.read_called

    service_response = FakeResponse()
    service_session = FakeSession(service_response)
    with patch(
        "custom_components.bods_bus_tracker.config_flow.async_get_clientsession",
        return_value=service_session,
    ):
        await _async_validate_api_key(hass, "abc", "ANUM|X14")

    assert "operatorRef=ANUM" in service_session.urls[0]
    assert "lineRef=X14" in service_session.urls[0]


async def test_generic_api_key_validator_maps_invalid_token_403_to_auth(hass) -> None:
    """BODS' real 403 invalid-token response is treated as invalid auth."""
    response = FakeResponse(403, b'{"detail":"Invalid token."}')
    session = FakeSession(response)

    with patch(
        "custom_components.bods_bus_tracker.config_flow.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(ClientResponseError) as exc_info:
            await _async_validate_api_key_generic(hass, "expired-key")

    assert exc_info.value.status == 401


async def test_auto_detect_skips_bad_region_and_finds_exact(hass) -> None:
    """Automatic exact-code search tolerates one unavailable regional GTFS."""
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow._region_search_order",
            return_value=["bad", "north_east"],
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(
                side_effect=[GTFSDownloadError("bad"), Path("/tmp/ne.zip")]
            ),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP,),
        ),
    ):
        result = await _async_auto_detect_stop(hass, STOP.stop_id)

    assert result == ("north_east", STOP)


async def test_auto_detect_returns_none_without_exact_match(hass) -> None:
    """A region search result that is not the requested exact code is ignored."""
    other = StopChoice("OTHER", "other", "Other", 55.0, -1.0)
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow._region_search_order",
            return_value=["north_east"],
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(other,),
        ),
    ):
        assert await _async_auto_detect_stop(hass, STOP.stop_id) is None


@pytest.mark.parametrize("error", [TimeoutError(), RuntimeError("boom")])
async def test_reauth_non_http_errors(hass, error: Exception) -> None:
    """Reauthentication reports transport and unexpected failures cleanly."""
    entry = _entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key_generic",
        new=AsyncMock(side_effect=error),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "replacement"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {
        "base": "cannot_connect" if isinstance(error, TimeoutError) else "unknown"
    }


async def _start_stop(hass, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": SOURCE_USER},
    )


@pytest.mark.parametrize(
    ("ensure_error", "search_result", "expected"),
    [
        (GTFSDownloadError("download"), None, "gtfs_download_failed"),
        (RuntimeError("boom"), None, "unknown"),
        (None, (), None),
    ],
)
async def test_stop_search_error_paths(
    hass, ensure_error, search_result, expected
) -> None:
    """Regional stop search handles download, unexpected and no-result cases."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)

    ensure = AsyncMock(
        side_effect=ensure_error if ensure_error is not None else None,
        return_value=Path("/tmp/ne.zip"),
    )
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=ensure,
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=search_result or (),
        ),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: "missing"},
        )

    assert result2["type"] is FlowResultType.FORM
    if expected:
        assert result2["errors"] == {"base": expected}
    else:
        assert result2["errors"] == {CONF_STOP_SEARCH: "stop_search_no_results"}


async def test_stop_with_no_services_returns_search_form(hass) -> None:
    """A found boarding point with no usable BODS operator IDs cannot be added."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP,),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=EMPTY_DISCOVERY,
        ),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: STOP.stop_id},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "no_services"}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ClientConnectionError("offline"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_service_validation_non_http_errors(hass, error: Exception, expected: str) -> None:
    """Adding a stop handles service-validation transport and unknown failures."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
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
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: STOP.stop_id},
        )

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
        new=AsyncMock(side_effect=error),
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


async def test_reconfigure_validation_branches(hass) -> None:
    """Reconfigure validates services and dynamic walking just like initial setup."""
    entry = _entry(walking_entity="sensor.old_walk")
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))

    async def start():
        return await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_STOP),
            context={
                "source": SOURCE_RECONFIGURE,
                "subentry_id": subentry.subentry_id,
            },
        )

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
    ):
        result = await start()
        assert result["type"] is FlowResultType.FORM

        no_service = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERVICES: [],
                CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
                CONF_WALKING_TIME: 5,
                CONF_DYNAMIC_WALKING_TIME: False,
                CONF_POLL_INTERVAL: 30,
            },
        )
        assert no_service["errors"] == {CONF_SERVICES: "select_service"}


@pytest.mark.parametrize(
    ("prepare_error", "reason"),
    [
        (GTFSDownloadError("bad feed"), "gtfs_download_failed"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reconfigure_prepare_failures(hass, prepare_error: Exception, reason: str) -> None:
    """Reconfigure aborts cleanly when its timetable cannot be prepared."""
    entry = _entry()
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))

    with patch(
        "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
        new=AsyncMock(side_effect=prepare_error),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_STOP),
            context={
                "source": SOURCE_RECONFIGURE,
                "subentry_id": subentry.subentry_id,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason



async def test_flow_level_duplicate_guard(hass) -> None:
    """The integration flow retains its own duplicate guard as defence in depth."""
    entry = _entry()
    entry.add_to_hass(hass)

    flow = BODSBusTrackerConfigFlow()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_already_configured"


@pytest.mark.parametrize(
    ("auto_result", "prepare_error", "expected"),
    [
        (RuntimeError("boom"), None, "unknown"),
        (None, None, "stop_not_found_all_regions"),
        (("north_east", STOP), GTFSDownloadError("bad"), "gtfs_download_failed"),
        (("north_east", STOP), RuntimeError("boom"), "unknown"),
    ],
)
async def test_auto_detect_failure_branches(
    hass, auto_result, prepare_error, expected: str
) -> None:
    """Auto-detection reports each discovery/preparation failure distinctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)

    auto_mock = (
        AsyncMock(side_effect=auto_result)
        if isinstance(auto_result, Exception)
        else AsyncMock(return_value=auto_result)
    )

    prepare_patch = patch(
        "custom_components.bods_bus_tracker.config_flow.BODSStopSubentryFlow._async_prepare_stop",
        new=AsyncMock(side_effect=prepare_error),
    )
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow._async_auto_detect_stop",
            new=auto_mock,
        ),
        prepare_patch,
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: AUTO_REGION, CONF_STOP_SEARCH: STOP.stop_id},
        )

    assert result2["type"] is FlowResultType.FORM
    if expected == "stop_not_found_all_regions":
        assert result2["errors"] == {CONF_STOP_SEARCH: expected}
    else:
        assert result2["errors"] == {"base": expected}


async def test_single_search_result_prepare_exception(hass) -> None:
    """An unexpected stop-preparation failure remains inside the flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP,),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.BODSStopSubentryFlow._async_prepare_stop",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: STOP.stop_id},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_stop_select_internal_invalid_guard(hass) -> None:
    """The handler also protects against stale selection data if called directly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    entry.add_to_hass(hass)

    flow = BODSStopSubentryFlow()
    flow.hass = hass
    flow.context = {
        "source": SOURCE_USER,
        "entry_id": entry.entry_id,
    }
    flow._data[CONF_REGION] = "north_east"
    flow._stop_results = (STOP,)

    result = await flow.async_step_stop_select(
        {CONF_STOP_SELECTION: "not-present"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_STOP_SELECTION: "stop_selection_invalid"}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (GTFSDownloadError("bad"), "gtfs_download_failed"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_stop_selection_prepare_failures(
    hass, error: Exception, expected: str
) -> None:
    """Selecting a valid listed stop handles preparation failures cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
    )
    result = await _start_stop(hass, entry)

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.search_stops",
            return_value=(STOP, StopChoice("OTHER", "", "Other", 55.0, -1.0)),
        ),
    ):
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_REGION: "north_east", CONF_STOP_SEARCH: "Stop"},
        )

    with patch(
        "custom_components.bods_bus_tracker.config_flow.BODSStopSubentryFlow._async_prepare_stop",
        new=AsyncMock(side_effect=error),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {CONF_STOP_SELECTION: STOP.stop_id},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected}


async def _start_reconfigure(hass, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP),
        context={
            "source": SOURCE_RECONFIGURE,
            "subentry_id": subentry.subentry_id,
        },
    )


async def test_reconfigure_dynamic_sensor_required(hass) -> None:
    """Reconfigure cannot enable routed walking without a source sensor."""
    entry = _entry()
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
    ):
        result = await _start_reconfigure(hass, entry)
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
    ("error", "expected"),
    [
        (ClientResponseError(None, (), status=403), "access_forbidden"),
        (ClientConnectionError("offline"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reconfigure_service_validation_errors(
    hass, error: Exception, expected: str
) -> None:
    """Reconfigure retains the current settings when validation fails."""
    entry = _entry()
    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow.async_ensure_gtfs",
            new=AsyncMock(return_value=Path("/tmp/ne.zip")),
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow.discover_stop_services",
            return_value=DISCOVERY,
        ),
        patch(
            "custom_components.bods_bus_tracker.config_flow._async_validate_api_key",
            new=AsyncMock(side_effect=error),
        ),
    ):
        result = await _start_reconfigure(hass, entry)
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
