"""Last-mile tests for complete integration line coverage.

These tests target defensive and recovery paths that are valid behaviour but rare in
normal operation. They intentionally do not alter production runtime behaviour.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
import zipfile

import pytest

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker import async_migrate_entry
from custom_components.bods_bus_tracker.api import (
    LiveVehicle,
    ServiceSpec,
    StopTime,
    Trip,
    build_gtfs_index,
    calculate_candidates,
    search_stops,
)
from custom_components.bods_bus_tracker.const import (
    CONF_API_KEY,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from custom_components.bods_bus_tracker.coordinator import BODSBusCoordinator
from custom_components.bods_bus_tracker.gtfs import (
    SharedGTFSRegionIndex,
    _atomic_write,
    _write_parsed_index,
)
from custom_components.bods_bus_tracker.live_feed import BODSLiveFeedResult

TZ = ZoneInfo("Europe/London")
DAY = date(2026, 9, 14)


def _service_trip(
    trip_id: str = "T1",
    *,
    origin_seconds: int = 13 * 3600,
    destination_seconds: int = 13 * 3600 + 300,
) -> Trip:
    return Trip(
        trip_id=trip_id,
        route="X18",
        operator_noc="ANUM",
        operator_name="Arriva",
        service_id="WK",
        headsign="Bus Station",
        vehicle_journey_code="1",
        stops=[
            StopTime("A", 1, origin_seconds, origin_seconds, 55.0, -1.0, "A"),
            StopTime(
                "B",
                2,
                destination_seconds,
                destination_seconds,
                55.1,
                -1.1,
                "B",
            ),
        ],
    )


def _entry_for_coordinator() -> MockConfigEntry:
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
                    CONF_STOP_NAME: "Test stop",
                    CONF_SERVICES: ["ANUM|X18"],
                    CONF_POLL_INTERVAL: 30,
                },
                subentry_id="stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="Test stop (B)",
                unique_id="north_east:B",
            )
        ],
    )


async def test_legacy_migration_moves_existing_device_to_stop_subentry(hass) -> None:
    """Migration preserves an existing legacy device by assigning the new subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy stop",
        data={
            CONF_API_KEY: "legacy-key",
            CONF_REGION: "north_east",
            CONF_STOP_ATCO: "3100Z199842",
            CONF_STOP_NAME: "The Fairway",
            CONF_SERVICES: ["ANUM|X18"],
        },
        options={CONF_POLL_INTERVAL: 30},
        version=1,
    )
    entry.add_to_hass(hass)

    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Legacy BODS stop",
    )

    with patch.object(
        registry,
        "async_update_device",
        wraps=registry.async_update_device,
    ) as update_device:
        assert await async_migrate_entry(hass, entry) is True

    subentry = next(iter(entry.subentries.values()))
    update_device.assert_any_call(
        device.id,
        new_config_subentry_id=subentry.subentry_id,
    )


async def test_coordinator_wraps_gtfs_refresh_failure(hass) -> None:
    """Unexpected GTFS refresh failures become translated UpdateFailed errors."""
    entry = _entry_for_coordinator()
    subentry = next(iter(entry.subentries.values()))
    coordinator = BODSBusCoordinator(
        hass,
        entry,
        subentry,
        MagicMock(),
        MagicMock(),
    )

    with patch.object(
        coordinator,
        "_async_refresh_gtfs_if_needed",
        new=AsyncMock(side_effect=RuntimeError("refresh failed")),
    ):
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


async def test_coordinator_collects_successful_siri_parse_and_warnings(hass) -> None:
    """A successful parser result contributes vehicles and parser warnings."""
    entry = _entry_for_coordinator()
    subentry = next(iter(entry.subentries.values()))
    live_feed = MagicMock()
    live_feed.async_get_operator = AsyncMock(
        return_value=BODSLiveFeedResult(payload=b"<Siri/>")
    )
    coordinator = BODSBusCoordinator(
        hass,
        entry,
        subentry,
        live_feed,
        MagicMock(),
    )

    vehicle = LiveVehicle(
        route="X18",
        operator_noc="ANUM",
        vehicle="v1",
        dated_ref="",
        origin_ref="A",
        destination_ref="B",
        origin_dt=datetime(2026, 9, 14, 13, 0, tzinfo=TZ),
        destination_dt=datetime(2026, 9, 14, 13, 5, tzinfo=TZ),
        recorded_dt=datetime(2026, 9, 14, 13, 1, tzinfo=TZ),
        lat=55.0,
        lon=-1.0,
        block_ref="",
        ticket_service="",
        journey_code="",
    )

    snapshot = {
        "health": "ok",
        "next_bus": {
            "available": False,
            "walking_minutes": 0,
        },
        "departures": [],
        "arrivals": [],
    }

    with (
        patch.object(
            coordinator,
            "_async_refresh_gtfs_if_needed",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.bods_bus_tracker.coordinator.parse_siri",
            return_value=([vehicle], None, ["parser warning"]),
        ),
        patch(
            "custom_components.bods_bus_tracker.coordinator.make_snapshot",
            return_value=snapshot,
        ) as make_snapshot,
        patch(
            "custom_components.bods_bus_tracker.coordinator.apply_stop_view",
            side_effect=lambda value, *args: value,
        ),
    ):
        await coordinator._async_update_data()

    args = make_snapshot.call_args.args
    assert args[2] == [vehicle]
    assert args[8] == ["parser warning"]


def test_search_stop_name_prefix_path(tmp_path: Path) -> None:
    """Name-prefix ranking is covered independently of stop-ID prefix ranking."""
    archive = tmp_path / "stops.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(
            "stops.txt",
            "stop_id,stop_code,stop_name,stop_lat,stop_lon\n"
            "ID1,sms1,Prefix Place,55.0,-1.0\n",
        )

    result = search_stops(archive, "Pref")

    assert result[0].stop_id == "ID1"


def _write_gtfs_with_missing_trip_rows(path: Path) -> None:
    """Write GTFS data containing one no-row trip and one unknown-stop trip."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("agency.txt", "agency_id,agency_name,agency_noc\nA,Arriva,ANUM\n")
        zf.writestr(
            "routes.txt",
            "route_id,agency_id,route_short_name\nR,A,X18\n",
        )
        zf.writestr(
            "trips.txt",
            "route_id,service_id,trip_id,trip_headsign,vehicle_journey_code\n"
            "R,WK,NO_ROWS,Town,1\n"
            "R,WK,MISSING_STOP,Town,2\n",
        )
        zf.writestr(
            "stop_times.txt",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            "MISSING_STOP,13:00:00,13:00:00,UNKNOWN,1\n",
        )
        zf.writestr(
            "stops.txt",
            "stop_id,stop_code,stop_name,stop_lat,stop_lon\n"
            "OTHER,sms,Other,55.0,-1.0\n",
        )
        zf.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WK,1,1,1,1,1,1,1,20260101,20261231\n",
        )
        zf.writestr(
            "calendar_dates.txt",
            "service_id,date,exception_type\n",
        )


def test_build_gtfs_skips_trip_without_rows_and_unknown_stop(tmp_path: Path) -> None:
    """Malformed selected trips are safely omitted from the parsed day index."""
    archive = tmp_path / "edge.zip"
    _write_gtfs_with_missing_trip_rows(archive)

    trips, info = build_gtfs_index(
        archive,
        DAY,
        "",
        [ServiceSpec("ANUM", "X18", "Arriva")],
    )

    assert trips == []
    assert info["skipped_bad_time_trips"] == 1


def test_realtime_candidate_already_stale_is_removed() -> None:
    """A live-matched journey with an already-past expected time is discarded."""
    trip = _service_trip()
    vehicle = LiveVehicle(
        route="X18",
        operator_noc="ANUM",
        vehicle="v1",
        dated_ref="",
        origin_ref="A",
        destination_ref="B",
        origin_dt=datetime(2026, 9, 14, 13, 0, tzinfo=TZ),
        destination_dt=datetime(2026, 9, 14, 13, 5, tzinfo=TZ),
        recorded_dt=datetime(2026, 9, 14, 13, 0, tzinfo=TZ),
        lat=55.0,
        lon=-1.0,
        block_ref="",
        ticket_service="",
        journey_code="",
    )

    candidates, stats = calculate_candidates(
        [trip],
        [vehicle],
        datetime(2026, 9, 14, 13, 10, tzinfo=TZ),
        "B",
        3600,
    )

    assert stats["matched_exact"] == 1
    assert candidates == []


def test_atomic_gtfs_cleanup_ignores_unlink_failure(tmp_path: Path) -> None:
    """A cleanup failure never masks the original invalid-download failure."""
    target = tmp_path / "feed.zip"

    with patch(
        "custom_components.bods_bus_tracker.gtfs.Path.unlink",
        side_effect=OSError("cleanup failed"),
    ):
        with pytest.raises(ValueError):
            _atomic_write(target, b"not-a-zip")


def test_index_cleanup_ignores_unlink_failure(tmp_path: Path) -> None:
    """Failed index replacement still tolerates failure deleting its temp file."""
    target = tmp_path / "feed.index.json"

    with (
        patch(
            "custom_components.bods_bus_tracker.gtfs.os.replace",
            side_effect=OSError("replace failed"),
        ),
        patch(
            "custom_components.bods_bus_tracker.gtfs.Path.unlink",
            side_effect=OSError("cleanup failed"),
        ),
    ):
        with pytest.raises(OSError, match="replace failed"):
            _write_parsed_index(
                target,
                {"size": 1, "mtime_ns": 2},
                DAY,
                ("ANUM|X18",),
                [_service_trip()],
                {"source": "test"},
            )


async def test_shared_gtfs_rechecks_unchanged_fingerprint_after_hour(
    hass, tmp_path: Path
) -> None:
    """The hourly fingerprint check reuses the in-memory parsed index when unchanged."""
    archive = tmp_path / "north_east.zip"
    # Fingerprinting only needs a stable file; the builder is patched below.
    archive.write_bytes(b"stable")
    trip = _service_trip()
    index = SharedGTFSRegionIndex(
        hass,
        "north_east",
        [ServiceSpec("ANUM", "X18", "Arriva")],
    )

    with (
        patch(
            "custom_components.bods_bus_tracker.gtfs.async_ensure_gtfs",
            new=AsyncMock(return_value=archive),
        ),
        patch(
            "custom_components.bods_bus_tracker.gtfs.build_gtfs_index",
            return_value=([trip], {"source": "test"}),
        ),
    ):
        first, _ = await index.async_get(DAY)
        index._last_check_monotonic = -10_000_000.0
        second, metadata = await index.async_get(DAY)

    assert second is first
    assert metadata["index_source"] == "memory"
