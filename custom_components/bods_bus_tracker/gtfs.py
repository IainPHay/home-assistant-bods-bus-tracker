"""GTFS cache and download helpers for BODS Bus Tracker."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable

from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ServiceSpec,
    StopTime,
    Trip,
    build_gtfs_index,
    make_service_key,
    validate_gtfs,
)
from .const import CACHE_DIR, DEFAULT_GTFS_REFRESH_HOURS, GTFS_URL_TEMPLATE, VERSION

_LOGGER = logging.getLogger(__name__)
_REGION_LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
GTFS_INDEX_CACHE_SCHEMA = 1


class GTFSDownloadError(Exception):
    """Raised when a GTFS region cannot be downloaded or validated."""


def gtfs_path(hass: HomeAssistant, region: str) -> Path:
    return Path(hass.config.path(CACHE_DIR, f"{region}.zip"))


def _is_cache_fresh(path: Path, refresh_hours: float) -> bool:
    if not path.exists():
        return False
    validate_gtfs(path)
    age_hours = (time.time() - path.stat().st_mtime) / 3600.0
    return age_hours < refresh_hours


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".gtfs-", suffix=".zip", delete=False
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(data)
        temp_path = Path(temp_name)
        validate_gtfs(temp_path)
        os.replace(temp_path, path)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


async def async_ensure_gtfs(
    hass: HomeAssistant,
    region: str,
    *,
    refresh_hours: float = DEFAULT_GTFS_REFRESH_HOURS,
) -> Path:
    """Return a valid cached regional GTFS, downloading if required."""
    path = gtfs_path(hass, region)
    async with _REGION_LOCKS[region]:
        try:
            fresh = await hass.async_add_executor_job(_is_cache_fresh, path, refresh_hours)
        except Exception:
            fresh = False
        if fresh:
            return path

        url = GTFS_URL_TEMPLATE.format(region=region)
        session = async_get_clientsession(hass)
        try:
            async with session.get(
                url,
                timeout=ClientTimeout(total=180),
                headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
            ) as response:
                response.raise_for_status()
                data = await response.read()
            await hass.async_add_executor_job(_atomic_write, path, data)
            return path
        except (ClientError, ClientResponseError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Unable to refresh BODS GTFS region %s: %s", region, exc)
            try:
                await hass.async_add_executor_job(validate_gtfs, path)
            except Exception as cache_exc:
                raise GTFSDownloadError(
                    f"Unable to download a valid GTFS feed for region {region}"
                ) from cache_exc
            return path


def _gtfs_fingerprint(path: Path) -> dict[str, int]:
    """Return a cheap fingerprint for the cached regional GTFS archive."""
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _index_cache_path(path: Path) -> Path:
    """Return the persistent parsed-index cache path beside the GTFS ZIP."""
    return path.with_suffix(".index.json")


def _trip_to_cache(trip: Trip) -> dict[str, object]:
    """Serialise a parsed trip without executable/pickle data."""
    return {
        "trip_id": trip.trip_id,
        "route": trip.route,
        "operator_noc": trip.operator_noc,
        "operator_name": trip.operator_name,
        "service_id": trip.service_id,
        "headsign": trip.headsign,
        "vehicle_journey_code": trip.vehicle_journey_code,
        "stops": [
            [
                stop.stop_id,
                stop.stop_sequence,
                stop.arrival_s,
                stop.departure_s,
                stop.lat,
                stop.lon,
                stop.name,
            ]
            for stop in trip.stops
        ],
    }


def _trip_from_cache(value: dict[str, object]) -> Trip:
    """Restore a parsed trip from the JSON cache."""
    stops_raw = value["stops"]
    if not isinstance(stops_raw, list):
        raise ValueError("Invalid GTFS parsed-index stops")
    stops = []
    for item in stops_raw:
        if not isinstance(item, list) or len(item) != 7:
            raise ValueError("Invalid GTFS parsed-index stop row")
        stops.append(
            StopTime(
                stop_id=str(item[0]),
                stop_sequence=int(item[1]),
                arrival_s=int(item[2]),
                departure_s=int(item[3]),
                lat=float(item[4]),
                lon=float(item[5]),
                name=str(item[6]),
            )
        )
    return Trip(
        trip_id=str(value["trip_id"]),
        route=str(value["route"]),
        operator_noc=str(value["operator_noc"]),
        operator_name=str(value["operator_name"]),
        service_id=str(value["service_id"]),
        headsign=str(value["headsign"]),
        vehicle_journey_code=str(value["vehicle_journey_code"]),
        stops=stops,
    )


def _load_parsed_index(
    cache_path: Path,
    fingerprint: dict[str, int],
    service_date: date,
    service_keys: tuple[str, ...],
) -> tuple[list[Trip], dict[str, object]] | None:
    """Load a parsed GTFS index only when its inputs still match exactly."""
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("schema") != GTFS_INDEX_CACHE_SCHEMA:
            return None
        if payload.get("gtfs") != fingerprint:
            return None
        if payload.get("service_date") != service_date.isoformat():
            return None
        if tuple(payload.get("services", ())) != service_keys:
            return None
        raw_trips = payload.get("trips")
        info = payload.get("info")
        if not isinstance(raw_trips, list) or not isinstance(info, dict):
            return None
        trips = [_trip_from_cache(item) for item in raw_trips if isinstance(item, dict)]
        if len(trips) != len(raw_trips):
            return None
        return trips, dict(info)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _write_parsed_index(
    cache_path: Path,
    fingerprint: dict[str, int],
    service_date: date,
    service_keys: tuple[str, ...],
    trips: list[Trip],
    info: dict[str, object],
) -> None:
    """Atomically persist the parsed service index for fast HA restarts."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": GTFS_INDEX_CACHE_SCHEMA,
        "gtfs": fingerprint,
        "service_date": service_date.isoformat(),
        "services": list(service_keys),
        "info": info,
        "trips": [_trip_to_cache(trip) for trip in trips],
    }
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_path.parent,
            prefix=".gtfs-index-",
            suffix=".json",
            delete=False,
        ) as temp_file:
            temp_name = temp_file.name
            json.dump(payload, temp_file, separators=(",", ":"))
        os.replace(temp_name, cache_path)
        temp_name = None
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


class SharedGTFSRegionIndex:
    """Share one parsed regional/service GTFS index across all configured stops."""

    def __init__(
        self,
        hass: HomeAssistant,
        region: str,
        services: Iterable[ServiceSpec],
    ) -> None:
        self.hass = hass
        self.region = region
        unique = {service.key: service for service in services}
        self.services = tuple(unique[key] for key in sorted(unique))
        self.service_keys = tuple(sorted(unique))
        self._lock = asyncio.Lock()
        self._trips: list[Trip] = []
        self._base_info: dict[str, object] = {}
        self._service_date: date | None = None
        self._fingerprint: dict[str, int] | None = None
        self._last_check_monotonic = 0.0
        self._generation = 0

    async def async_get(
        self, service_date: date
    ) -> tuple[list[Trip], dict[str, object]]:
        """Return the shared parsed index, rebuilding only when inputs change."""
        started = time.perf_counter()
        async with self._lock:
            now_monotonic = time.monotonic()
            if (
                self._service_date == service_date
                and self._trips
                and now_monotonic - self._last_check_monotonic < 3600
            ):
                return self._trips, self._metadata(
                    "memory", time.perf_counter() - started
                )

            path = await async_ensure_gtfs(self.hass, self.region)
            fingerprint = await self.hass.async_add_executor_job(
                _gtfs_fingerprint, path
            )
            self._last_check_monotonic = time.monotonic()

            if (
                self._service_date == service_date
                and self._trips
                and self._fingerprint == fingerprint
            ):
                return self._trips, self._metadata(
                    "memory", time.perf_counter() - started
                )

            cache_path = _index_cache_path(path)
            loaded = await self.hass.async_add_executor_job(
                _load_parsed_index,
                cache_path,
                fingerprint,
                service_date,
                self.service_keys,
            )
            source = "disk"
            if loaded is None:
                build_started = time.perf_counter()
                trips, info = await self.hass.async_add_executor_job(
                    build_gtfs_index,
                    path,
                    service_date,
                    "",
                    self.services,
                )
                build_seconds = time.perf_counter() - build_started
                info = dict(info)
                info.pop("target_trip_count", None)
                info["index_build_seconds"] = round(build_seconds, 3)
                await self.hass.async_add_executor_job(
                    _write_parsed_index,
                    cache_path,
                    fingerprint,
                    service_date,
                    self.service_keys,
                    trips,
                    info,
                )
                source = "rebuilt"
            else:
                trips, info = loaded

            self._trips = trips
            self._base_info = dict(info)
            self._service_date = service_date
            self._fingerprint = fingerprint
            self._generation += 1
            return self._trips, self._metadata(
                source, time.perf_counter() - started
            )

    def _metadata(self, source: str, prepare_seconds: float) -> dict[str, object]:
        """Return shared-index diagnostics without mutating cached base data."""
        return {
            **self._base_info,
            "shared_service_count": len(self.services),
            "shared_trip_count": len(self._trips),
            "index_source": source,
            "index_prepare_seconds": round(prepare_seconds, 3),
            "index_generation": self._generation,
        }
