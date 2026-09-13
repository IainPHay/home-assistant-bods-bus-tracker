"""GTFS download, persistence and shared-index tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO
import os
from pathlib import Path
import time
from unittest.mock import AsyncMock, MagicMock, patch
import zipfile

from aiohttp import ClientConnectionError
import pytest

from custom_components.bods_bus_tracker.api import ServiceSpec, StopTime, Trip
from custom_components.bods_bus_tracker.gtfs import (
    GTFSDownloadError,
    SharedGTFSRegionIndex,
    _gtfs_fingerprint,
    _index_cache_path,
    _is_cache_fresh,
    _load_parsed_index,
    _trip_from_cache,
    _trip_to_cache,
    _write_parsed_index,
    async_ensure_gtfs,
    gtfs_path,
)


DAY = date(2026, 9, 11)


def _valid_gtfs_bytes() -> bytes:
    """Return the smallest archive satisfying structural GTFS validation."""
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as zf:
        zf.writestr("agency.txt", "agency_id,agency_name,agency_noc\n")
        zf.writestr("routes.txt", "route_id,agency_id,route_short_name\n")
        zf.writestr("trips.txt", "route_id,service_id,trip_id\n")
        zf.writestr(
            "stop_times.txt",
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n",
        )
        zf.writestr(
            "stops.txt",
            "stop_id,stop_code,stop_name,stop_lat,stop_lon\n",
        )
        zf.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n",
        )
        zf.writestr(
            "calendar_dates.txt",
            "service_id,date,exception_type\n",
        )
    return stream.getvalue()


def _trip() -> Trip:
    return Trip(
        trip_id="T14",
        route="X14",
        operator_noc="ANUM",
        operator_name="Arriva",
        service_id="WK",
        headsign="Newcastle",
        vehicle_journey_code="1401",
        stops=[
            StopTime("A", 1, 36000, 36000, 55.0, -1.0, "Origin"),
            StopTime("B", 2, 36600, 36600, 55.1, -1.1, "The Fairway"),
        ],
    )


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.status = 200
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    async def read(self) -> bytes:
        return self.payload


class FakeSession:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def test_cache_helpers_round_trip(tmp_path: Path) -> None:
    """Parsed trip JSON is safe, deterministic and input-keyed."""
    archive = tmp_path / "north_east.zip"
    archive.write_bytes(_valid_gtfs_bytes())
    fingerprint = _gtfs_fingerprint(archive)
    assert fingerprint["size"] > 0
    assert _index_cache_path(archive).name == "north_east.index.json"

    original = _trip()
    encoded = _trip_to_cache(original)
    restored = _trip_from_cache(encoded)
    assert restored.trip_id == original.trip_id
    assert restored.stops[1].name == "The Fairway"

    with pytest.raises(ValueError):
        _trip_from_cache({**encoded, "stops": "bad"})
    with pytest.raises(ValueError):
        _trip_from_cache({**encoded, "stops": [["too", "short"]]})

    cache = _index_cache_path(archive)
    services = ("ANUM|X14",)
    info = {"service_date": DAY.isoformat(), "relevant_trip_count": 1}
    _write_parsed_index(cache, fingerprint, DAY, services, [original], info)

    loaded = _load_parsed_index(cache, fingerprint, DAY, services)
    assert loaded is not None
    trips, loaded_info = loaded
    assert trips[0].trip_id == "T14"
    assert loaded_info == info

    assert _load_parsed_index(
        cache,
        {**fingerprint, "mtime_ns": fingerprint["mtime_ns"] + 1},
        DAY,
        services,
    ) is None


def test_cache_freshness(tmp_path: Path) -> None:
    """Fresh valid GTFS archives are reused while stale ones refresh."""
    archive = tmp_path / "feed.zip"
    archive.write_bytes(_valid_gtfs_bytes())

    assert _is_cache_fresh(archive, 24) is True
    old = time.time() - 48 * 3600
    os.utime(archive, (old, old))
    assert _is_cache_fresh(archive, 24) is False
    assert _is_cache_fresh(tmp_path / "missing.zip", 24) is False


async def test_async_ensure_gtfs_uses_fresh_cache(hass) -> None:
    """No network request occurs for a fresh validated regional cache."""
    path = gtfs_path(hass, "north_east")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_valid_gtfs_bytes())

    with patch(
        "custom_components.bods_bus_tracker.gtfs.async_get_clientsession"
    ) as session:
        result = await async_ensure_gtfs(hass, "north_east", refresh_hours=24)

    assert result == path
    session.assert_not_called()


async def test_async_ensure_gtfs_downloads_stale_or_missing_cache(hass) -> None:
    """A missing cache is atomically replaced with a validated download."""
    session = FakeSession(FakeResponse(_valid_gtfs_bytes()))
    with patch(
        "custom_components.bods_bus_tracker.gtfs.async_get_clientsession",
        return_value=session,
    ):
        path = await async_ensure_gtfs(hass, "east_anglia", refresh_hours=0)

    assert path.exists()
    assert zipfile.is_zipfile(path)
    assert session.calls == 1


async def test_async_ensure_gtfs_falls_back_to_valid_old_cache(hass) -> None:
    """Network failure retains a previously valid regional archive."""
    path = gtfs_path(hass, "north_west")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_valid_gtfs_bytes())

    session = FakeSession(ClientConnectionError("offline"))
    with patch(
        "custom_components.bods_bus_tracker.gtfs.async_get_clientsession",
        return_value=session,
    ):
        result = await async_ensure_gtfs(hass, "north_west", refresh_hours=0)

    assert result == path


async def test_async_ensure_gtfs_raises_without_valid_cache(hass) -> None:
    """No valid download and no valid cache becomes ConfigEntryNotReady upstream."""
    session = FakeSession(ClientConnectionError("offline"))
    with patch(
        "custom_components.bods_bus_tracker.gtfs.async_get_clientsession",
        return_value=session,
    ):
        with pytest.raises(GTFSDownloadError):
            await async_ensure_gtfs(hass, "south_west", refresh_hours=0)


async def test_shared_region_index_rebuild_memory_and_disk(hass, tmp_path: Path) -> None:
    """One parse is shared in memory and then persisted across manager instances."""
    archive = tmp_path / "north_east.zip"
    archive.write_bytes(_valid_gtfs_bytes())
    services = [ServiceSpec("ANUM", "X14")]
    trip = _trip()
    info = {
        "service_date": DAY.isoformat(),
        "relevant_trip_count": 1,
        "target_trip_count": 1,
        "skipped_bad_time_trips": 0,
    }

    first = SharedGTFSRegionIndex(hass, "north_east", services)
    with (
        patch(
            "custom_components.bods_bus_tracker.gtfs.async_ensure_gtfs",
            new=AsyncMock(return_value=archive),
        ),
        patch(
            "custom_components.bods_bus_tracker.gtfs.build_gtfs_index",
            return_value=([trip], info),
        ) as build,
    ):
        trips1, meta1 = await first.async_get(DAY)
        trips2, meta2 = await first.async_get(DAY)

    assert trips1[0].trip_id == "T14"
    assert meta1["index_source"] == "rebuilt"
    assert meta1["shared_service_count"] == 1
    assert meta2["index_source"] == "memory"
    assert build.call_count == 1

    second = SharedGTFSRegionIndex(hass, "north_east", services)
    with (
        patch(
            "custom_components.bods_bus_tracker.gtfs.async_ensure_gtfs",
            new=AsyncMock(return_value=archive),
        ),
        patch(
            "custom_components.bods_bus_tracker.gtfs.build_gtfs_index",
        ) as build_again,
    ):
        trips3, meta3 = await second.async_get(DAY)

    assert trips3[0].trip_id == "T14"
    assert meta3["index_source"] == "disk"
    build_again.assert_not_called()
