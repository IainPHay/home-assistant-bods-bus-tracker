"""Targeted edge tests for Integration Quality Scale coverage gates."""

from __future__ import annotations

import io
import json
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
import zipfile

from aiohttp import ClientResponseError
import pytest

from homeassistant.config_entries import ConfigSubentryData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker import BODSBusRuntimeData
from custom_components.bods_bus_tracker.api import (
    LiveVehicle,
    StopChoice,
    StopTime,
    Trip,
    _calling_trip_ids_for_stop,
    _stop_metadata,
    fuzzy_match_trip,
    validate_gtfs,
)
from custom_components.bods_bus_tracker.binary_sensor import LeaveNowBinarySensor
from custom_components.bods_bus_tracker.catchable import apply_catchable_guidance
from custom_components.bods_bus_tracker.config_flow import _async_validate_api_key
from custom_components.bods_bus_tracker.const import (
    CONF_API_KEY,
    CONF_LEGACY_ENTITY_IDS,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from custom_components.bods_bus_tracker.gtfs import (
    _load_parsed_index,
    async_ensure_gtfs,
)
from custom_components.bods_bus_tracker.gtfs_cache_model import (
    GTFS_INDEX_CACHE_SCHEMA,
    cache_matches_inputs,
)
from custom_components.bods_bus_tracker.live_feed import (
    BODSLiveFeedClient,
    BODSLiveFeedResult,
)
from custom_components.bods_bus_tracker.live_feed_model import (
    bods_payload_is_invalid_token,
)


TZ = ZoneInfo("Europe/London")


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, payload: bytes = b"ok") -> None:
        self.status = status
        self.payload = payload
        self.request_info = MagicMock()
        self.history = ()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def read(self) -> bytes:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(self.request_info, self.history, status=self.status)


class SequenceSession:
    """Return configured responses/exceptions in request order."""

    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.mark.parametrize(
    ("probe_response", "expected_status"),
    [
        (FakeResponse(200, b"ok"), 403),
        (FakeResponse(401, b"invalid"), 401),
    ],
)
async def test_service_validation_403_probe_paths(
    hass, probe_response: FakeResponse, expected_status: int
) -> None:
    """A plain service 403 is independently probed before deciding reauth."""
    session = SequenceSession(
        FakeResponse(403, b"forbidden"),
        probe_response,
    )
    with patch(
        "custom_components.bods_bus_tracker.config_flow.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(ClientResponseError) as exc_info:
            await _async_validate_api_key(hass, "key", "ANUM|X14")

    assert exc_info.value.status == expected_status
    assert session.calls == 2


async def test_live_feed_invalid_token_probe_401_and_failures(hass) -> None:
    """The secondary token probe handles explicit 401 and local failures."""
    client = BODSLiveFeedClient(hass, "key")

    assert await client._async_api_key_is_invalid(
        SequenceSession(FakeResponse(401, b"invalid"))
    )

    assert not await client._async_api_key_is_invalid(
        SequenceSession(TimeoutError())
    )

    assert not await client._async_api_key_is_invalid(
        SequenceSession(RuntimeError("unexpected"))
    )


async def test_live_feed_inner_cache_and_request_spacing(hass) -> None:
    """The locked fetch path rechecks cache and honours global request spacing."""
    client = BODSLiveFeedClient(hass, "key")
    loop = __import__("asyncio").get_running_loop()
    cached = BODSLiveFeedResult(payload=b"cached")
    client._cache["ANUM"] = (loop.time(), cached)

    assert await client._async_fetch_operator("ANUM") is cached

    client._cache.clear()
    client._last_request_started = loop.time()
    session = SequenceSession(FakeResponse(200, b"fresh"))
    sleeper = AsyncMock()
    with (
        patch(
            "custom_components.bods_bus_tracker.live_feed.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.bods_bus_tracker.live_feed.asyncio.sleep",
            new=sleeper,
        ),
    ):
        result = await client._async_fetch_operator("ANUM")

    assert result == BODSLiveFeedResult(payload=b"fresh")
    sleeper.assert_awaited_once()


def test_catchable_skips_invalid_rows_and_accepts_naive_time() -> None:
    """Malformed rows are skipped and a naive valid time adopts local tzinfo."""
    now = datetime(2026, 9, 14, 10, 0, tzinfo=TZ)
    snapshot = {
        "departures": [
            "not-a-row",
            {"route": "bad", "expected": None, "scheduled": "not-a-time"},
            {
                "route": "X18",
                "expected": "2026-09-14T10:15:00",
                "scheduled": "2026-09-14T10:15:00",
            },
        ]
    }

    result = apply_catchable_guidance(snapshot, now, walking_minutes=5)["catchable"]

    assert result["status"] == "ok"
    assert result["departure"]["route"] == "X18"


def test_cache_policy_rejects_non_list_services() -> None:
    """Persistent cache services must use the JSON list shape."""
    payload = {
        "schema": GTFS_INDEX_CACHE_SCHEMA,
        "gtfs": {"size": 1, "mtime_ns": 2},
        "service_date": "2026-09-14",
        "services": ("ANUM|X18",),
    }

    assert not cache_matches_inputs(
        payload,
        {"size": 1, "mtime_ns": 2},
        "2026-09-14",
        ("ANUM|X18",),
    )


def test_live_feed_token_helper_rejects_missing_payload() -> None:
    """No response payload cannot independently prove an invalid token."""
    assert bods_payload_is_invalid_token(None) is False


def test_binary_sensor_legacy_identity_and_device_info() -> None:
    """Migrated stops retain their legacy entity/device identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "key"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_REGION: "north_east",
                    CONF_STOP_ATCO: "3100Z199842",
                    CONF_STOP_NAME: "The Fairway",
                    CONF_SERVICES: ["ANUM|X18"],
                    CONF_LEGACY_ENTITY_IDS: True,
                },
                subentry_id="legacy-stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (3100Z199842)",
                unique_id="north_east:3100Z199842",
            )
        ],
    )
    subentry = next(iter(entry.subentries.values()))
    coordinator = MagicMock()
    coordinator.data = {"next_bus": {}}
    coordinator.last_update_success = True

    entity = LeaveNowBinarySensor(coordinator, entry, subentry)

    assert entity.unique_id == f"{entry.entry_id}_leave_now"
    assert entity.device_info["identifiers"] == {(DOMAIN, entry.entry_id)}


def test_api_small_edge_branches(tmp_path) -> None:
    """Exercise inexpensive parser/matching branches that guard malformed data."""
    choice = StopChoice("STOP", "sms", "Example", 55.0, -1.0, distance_km=1.25)
    assert "1.2 km from Home Assistant" in choice.label

    bad_zip = tmp_path / "missing-files.zip"
    with zipfile.ZipFile(bad_zip, "w") as archive:
        archive.writestr("stops.txt", "stop_id,stop_name\nSTOP,Example\n")
    with pytest.raises(ValueError, match="GTFS archive missing"):
        validate_gtfs(bad_zip)

    assert _calling_trip_ids_for_stop(io.BytesIO(b""), "STOP", {"T1"}) == set()
    short = io.BytesIO(b"trip_id,x,stop_id\nT1,STOP\n")
    assert _calling_trip_ids_for_stop(short, "STOP", {"T1"}) == set()

    stop_a = StopTime("A", 1, 0, 0, 55.0, -1.0, "A")
    stop_b = StopTime("B", 2, 60, 60, 55.1, -1.1, "B")
    stop_c = StopTime("C", 2, 60, 60, 55.2, -1.2, "C")
    trip_wrong_origin = Trip("t1", "X18", "ANUM", "Arriva", "svc", "B", "", [stop_c, stop_b])
    trip_wrong_destination = Trip("t2", "X18", "ANUM", "Arriva", "svc", "C", "", [stop_a, stop_c])
    vehicle = LiveVehicle(
        route="X18",
        operator_noc="ANUM",
        vehicle="v",
        dated_ref="",
        origin_ref="A",
        destination_ref="B",
        origin_dt=datetime(2026, 9, 14, 10, 0, tzinfo=TZ),
        destination_dt=datetime(2026, 9, 14, 11, 0, tzinfo=TZ),
        recorded_dt=datetime(2026, 9, 14, 10, 10, tzinfo=TZ),
        lat=55.0,
        lon=-1.0,
        block_ref="",
        ticket_service="",
        journey_code="",
    )
    assert fuzzy_match_trip(
        vehicle,
        [trip_wrong_origin, trip_wrong_destination],
        date(2026, 9, 14),
    ) == (None, "unmatched")

    trip_without_target = Trip("t3", "X18", "ANUM", "Arriva", "svc", "B", "", [stop_a, stop_b])
    trip_with_target = Trip(
        "t4",
        "X18",
        "ANUM",
        "Arriva",
        "svc",
        "STOP",
        "",
        [stop_a, StopTime("STOP", 2, 60, 60, 55.1234567, -1.7654321, "Target")],
    )
    assert _stop_metadata(
        [trip_without_target, trip_with_target], "STOP", "Target"
    )["latitude"] == 55.123457


def test_parsed_index_rejects_wrong_payload_shapes(tmp_path) -> None:
    """Disk cache loader rejects valid metadata with unusable trip shapes."""
    cache = tmp_path / "feed.index.json"
    fingerprint = {"size": 1, "mtime_ns": 2}
    service_date = date(2026, 9, 14)
    services = ("ANUM|X18",)

    base = {
        "schema": GTFS_INDEX_CACHE_SCHEMA,
        "gtfs": fingerprint,
        "service_date": service_date.isoformat(),
        "services": list(services),
        "info": {},
    }

    cache.write_text(json.dumps({**base, "trips": "wrong"}), encoding="utf-8")
    assert _load_parsed_index(cache, fingerprint, service_date, services) is None

    cache.write_text(json.dumps({**base, "trips": [None]}), encoding="utf-8")
    assert _load_parsed_index(cache, fingerprint, service_date, services) is None


async def test_gtfs_freshness_check_failure_falls_through_to_download(
    hass, tmp_path
) -> None:
    """A broken cache freshness check must not prevent a clean refresh."""
    target = tmp_path / "north_east.zip"
    session = SequenceSession(FakeResponse(200, b"zip-bytes"))
    executor = AsyncMock(side_effect=[RuntimeError("bad cache"), None])

    with (
        patch(
            "custom_components.bods_bus_tracker.gtfs.gtfs_path",
            return_value=target,
        ),
        patch(
            "custom_components.bods_bus_tracker.gtfs.async_get_clientsession",
            return_value=session,
        ),
        patch.object(hass, "async_add_executor_job", new=executor),
    ):
        result = await async_ensure_gtfs(hass, "north_east")

    assert result == target
    assert session.calls == 1
