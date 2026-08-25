"""BODS/GTFS parsing and ETA calculation for BODS Bus Tracker.

This module intentionally contains no Home Assistant imports so the matching and ETA
engine can be regression-tested independently.
"""

from __future__ import annotations

import csv
import io
import math
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from .const import LOCAL_TIME_ZONE, SERVICE_SEPARATOR

LOCAL_TZ = ZoneInfo(LOCAL_TIME_ZONE)
SIRI_NS = {"s": "http://www.siri.org.uk/siri"}
REQUIRED_GTFS = {
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar.txt",
    "calendar_dates.txt",
}


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    """A route/operator pair selected by the user."""

    operator_noc: str
    route: str
    operator_name: str = ""

    @property
    def key(self) -> str:
        return make_service_key(self.operator_noc, self.route)


@dataclass(frozen=True, slots=True)
class ServiceChoice:
    """A route/operator choice discovered at a stop."""

    operator_noc: str
    route: str
    operator_name: str
    headsigns: tuple[str, ...]

    @property
    def key(self) -> str:
        return make_service_key(self.operator_noc, self.route)

    @property
    def label(self) -> str:
        operator = self.operator_name or self.operator_noc
        heads = ", ".join(self.headsigns[:3])
        suffix = f" — {heads}" if heads else ""
        return f"{self.route} — {operator}{suffix}"


@dataclass(frozen=True, slots=True)
class StopChoice:
    """A stop returned by setup-time GTFS search."""

    stop_id: str
    stop_code: str
    stop_name: str
    lat: float
    lon: float
    distance_km: float | None = None

    @property
    def label(self) -> str:
        parts = [self.stop_name, self.stop_id]
        if self.stop_code:
            parts.append(self.stop_code)
        label = " — ".join(parts)
        if self.distance_km is not None:
            label += f" — {self.distance_km:.1f} km from Home Assistant"
        return label


@dataclass(frozen=True, slots=True)
class StopDiscovery:
    stop_id: str
    stop_name: str
    services: tuple[ServiceChoice, ...]


@dataclass(slots=True)
class StopTime:
    stop_id: str
    stop_sequence: int
    arrival_s: int
    departure_s: int
    lat: float
    lon: float
    name: str


@dataclass(slots=True)
class Trip:
    trip_id: str
    route: str
    operator_noc: str
    operator_name: str
    service_id: str
    headsign: str
    vehicle_journey_code: str
    stops: list[StopTime]

    @property
    def origin(self) -> StopTime:
        return self.stops[0]

    @property
    def destination(self) -> StopTime:
        return self.stops[-1]

    def target(self, stop_id: str) -> StopTime | None:
        return next((stop for stop in self.stops if stop.stop_id == stop_id), None)


@dataclass(slots=True)
class LiveVehicle:
    route: str
    operator_noc: str
    vehicle: str
    dated_ref: str
    origin_ref: str
    destination_ref: str
    origin_dt: datetime
    destination_dt: datetime
    recorded_dt: datetime
    lat: float
    lon: float
    block_ref: str
    ticket_service: str
    journey_code: str


@dataclass(slots=True)
class Candidate:
    service_key: str
    operator_noc: str
    operator_name: str
    route: str
    trip_id: str
    destination: str
    scheduled: datetime
    expected: datetime
    realtime: bool
    vehicle: str | None = None
    delay_minutes: float | None = None
    raw_delay_minutes: float | None = None
    timing_status: str | None = None
    stop_role: str = "intermediate"
    prediction_clamped: bool = False
    last_update: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    position_to_route_m: float | None = None


def make_service_key(operator_noc: str, route: str) -> str:
    return f"{operator_noc}{SERVICE_SEPARATOR}{route}"


def parse_service_key(value: str) -> ServiceSpec:
    parts = value.split(SERVICE_SEPARATOR, 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(f"Invalid service key: {value!r}")
    return ServiceSpec(parts[0].strip(), parts[1].strip())


def hms_to_seconds(value: str) -> int:
    parts = (value or "").split(":")
    if len(parts) != 3:
        raise ValueError(f"invalid GTFS time {value!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_hms(seconds: int) -> str:
    seconds %= 24 * 3600
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def service_datetime(service_date: date, seconds: int) -> datetime:
    midnight = datetime.combine(service_date, datetime.min.time(), tzinfo=LOCAL_TZ)
    return midnight + timedelta(seconds=seconds)


def validate_gtfs(path: Path, target_stop: str | None = None) -> None:
    """Validate the basic GTFS archive and optionally a stop ID."""
    if not zipfile.is_zipfile(path):
        raise ValueError("download is not a valid ZIP archive")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        missing = sorted(REQUIRED_GTFS - names)
        if missing:
            raise ValueError(f"GTFS archive missing: {', '.join(missing)}")
        if target_stop is None:
            return
        with zf.open("stops.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                if row.get("stop_id") == target_stop:
                    return
        raise ValueError(f"GTFS archive does not contain stop {target_stop}")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres."""
    earth_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * earth_km * math.asin(math.sqrt(a))


def is_probable_stop_code(value: str) -> bool:
    """Return True for strings that plausibly represent ATCO/NaPTAN codes."""
    compact = (value or "").strip()
    return 5 <= len(compact) <= 16 and compact.isalnum()


def search_stops(
    gtfs_path: Path,
    query: str,
    limit: int = 25,
    home_lat: float | None = None,
    home_lon: float | None = None,
) -> tuple[StopChoice, ...]:
    """Search a regional GTFS stops file by ATCO, NaPTAN code or stop name."""
    query = (query or "").strip()
    if not query:
        return ()
    query_cf = query.casefold()
    tokens = [token for token in query_cf.replace(",", " ").split() if token]
    results: list[tuple[int, float, StopChoice]] = []

    with zipfile.ZipFile(gtfs_path) as zf:
        with zf.open("stops.txt") as file_handle:
            reader = csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig"))
            for row in reader:
                stop_id = (row.get("stop_id") or "").strip()
                stop_code = (row.get("stop_code") or "").strip()
                stop_name = (row.get("stop_name") or stop_id).strip()
                if not stop_id:
                    continue
                sid = stop_id.casefold()
                scode = stop_code.casefold()
                sname = stop_name.casefold()

                name_words = {word.strip(".,/()-") for word in sname.split()}
                if query_cf == sid or (scode and query_cf == scode):
                    score = 0
                elif sid.startswith(query_cf) or (scode and scode.startswith(query_cf)):
                    score = 5
                elif query_cf == sname:
                    score = 10
                elif len(tokens) == 1 and tokens[0] in name_words:
                    score = 15
                elif sname.startswith(query_cf):
                    score = 20
                elif tokens and all(
                    token in f"{sname} {sid} {scode}" for token in tokens
                ):
                    score = 30
                elif query_cf in sname:
                    score = 40
                else:
                    continue

                try:
                    lat = float(row.get("stop_lat") or "")
                    lon = float(row.get("stop_lon") or "")
                except ValueError:
                    continue
                distance = None
                if home_lat is not None and home_lon is not None:
                    distance = _haversine_km(home_lat, home_lon, lat, lon)
                choice = StopChoice(
                    stop_id=stop_id,
                    stop_code=stop_code,
                    stop_name=stop_name,
                    lat=lat,
                    lon=lon,
                    distance_km=distance,
                )
                results.append((score, distance if distance is not None else 1e9, choice))

    results.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2].stop_name.casefold(),
            item[2].stop_id,
        )
    )
    return tuple(item[2] for item in results[:limit])


def discover_stop_services(gtfs_path: Path, stop_id: str) -> StopDiscovery:
    """Find a stop and the operator/route pairs that call there."""
    with zipfile.ZipFile(gtfs_path) as zf:
        stop_name: str | None = None
        with zf.open("stops.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                if row.get("stop_id") == stop_id:
                    stop_name = row.get("stop_name") or stop_id
                    break
        if stop_name is None:
            raise LookupError(f"Stop {stop_id} was not found in this GTFS region")

        agencies: dict[str, tuple[str, str]] = {}
        with zf.open("agency.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                agency_id = row.get("agency_id", "")
                noc = row.get("agency_noc", "").strip()
                name = row.get("agency_name", "").strip()
                if agency_id and noc:
                    agencies[agency_id] = (noc, name)

        routes: dict[str, tuple[str, str, str]] = {}
        with zf.open("routes.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                agency = agencies.get(row.get("agency_id", ""))
                route_short_name = row.get("route_short_name", "").strip()
                if agency and route_short_name:
                    routes[row["route_id"]] = (route_short_name, agency[0], agency[1])

        trips: dict[str, tuple[str, str]] = {}
        with zf.open("trips.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                if row.get("route_id") in routes:
                    trips[row["trip_id"]] = (
                        row["route_id"],
                        row.get("trip_headsign", "").strip(),
                    )

        calling_trip_ids: set[str] = set()
        with zf.open("stop_times.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                if row.get("stop_id") == stop_id and row.get("trip_id") in trips:
                    calling_trip_ids.add(row["trip_id"])

    discovered: dict[tuple[str, str], dict[str, object]] = {}
    for trip_id in calling_trip_ids:
        route_id, headsign = trips[trip_id]
        route, noc, operator_name = routes[route_id]
        key = (noc, route)
        item = discovered.setdefault(
            key,
            {"operator_name": operator_name, "headsigns": set()},
        )
        if headsign:
            cast_set = item["headsigns"]
            assert isinstance(cast_set, set)
            cast_set.add(headsign)

    choices = []
    for (noc, route), item in discovered.items():
        headsigns_obj = item["headsigns"]
        assert isinstance(headsigns_obj, set)
        choices.append(
            ServiceChoice(
                operator_noc=noc,
                route=route,
                operator_name=str(item["operator_name"]),
                headsigns=tuple(sorted(str(value) for value in headsigns_obj)),
            )
        )
    choices.sort(key=lambda choice: (choice.route.casefold(), choice.operator_name.casefold()))
    return StopDiscovery(stop_id=stop_id, stop_name=stop_name, services=tuple(choices))


def active_services_for_date(zf: zipfile.ZipFile, service_date: date) -> set[str]:
    ymd = service_date.strftime("%Y%m%d")
    weekday = (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )[service_date.weekday()]

    active: set[str] = set()
    with zf.open("calendar.txt") as file_handle:
        for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
            if row["start_date"] <= ymd <= row["end_date"] and row[weekday] == "1":
                active.add(row["service_id"])

    with zf.open("calendar_dates.txt") as file_handle:
        for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
            if row["date"] != ymd:
                continue
            if row["exception_type"] == "1":
                active.add(row["service_id"])
            elif row["exception_type"] == "2":
                active.discard(row["service_id"])

    return active


def build_gtfs_index(
    gtfs_path: Path,
    service_date: date,
    target_stop: str,
    services: Iterable[ServiceSpec],
) -> tuple[list[Trip], dict[str, object]]:
    """Build the day-specific GTFS index for selected services."""
    selected = {(service.operator_noc, service.route) for service in services}
    with zipfile.ZipFile(gtfs_path) as zf:
        active_services = active_services_for_date(zf, service_date)

        agency_meta: dict[str, tuple[str, str]] = {}
        with zf.open("agency.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                noc = row.get("agency_noc", "").strip()
                if noc and any(service_noc == noc for service_noc, _ in selected):
                    agency_meta[row["agency_id"]] = (noc, row.get("agency_name", "").strip())

        route_by_id: dict[str, tuple[str, str, str]] = {}
        with zf.open("routes.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                agency = agency_meta.get(row.get("agency_id", ""))
                route = row.get("route_short_name", "").strip()
                if agency and (agency[0], route) in selected:
                    route_by_id[row["route_id"]] = (route, agency[0], agency[1])

        trip_meta: dict[str, dict[str, str]] = {}
        with zf.open("trips.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                route_meta = route_by_id.get(row.get("route_id", ""))
                if route_meta is None or row.get("service_id") not in active_services:
                    continue
                route, noc, operator_name = route_meta
                trip_meta[row["trip_id"]] = {
                    "route": route,
                    "operator_noc": noc,
                    "operator_name": operator_name,
                    "service_id": row["service_id"],
                    "headsign": row.get("trip_headsign", ""),
                    "vehicle_journey_code": row.get("vehicle_journey_code", ""),
                }

        stop_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
        relevant_trip_ids = set(trip_meta)
        with zf.open("stop_times.txt") as file_handle:
            reader = csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig"))
            for row in reader:
                if row.get("trip_id") in relevant_trip_ids:
                    stop_rows[row["trip_id"]].append(row)

        needed_stop_ids = {row["stop_id"] for rows in stop_rows.values() for row in rows}
        stop_meta: dict[str, dict[str, str]] = {}
        with zf.open("stops.txt") as file_handle:
            for row in csv.DictReader(io.TextIOWrapper(file_handle, "utf-8-sig")):
                if row.get("stop_id") in needed_stop_ids:
                    stop_meta[row["stop_id"]] = row

    trips: list[Trip] = []
    skipped_bad_times = 0
    for trip_id, meta in trip_meta.items():
        rows = stop_rows.get(trip_id, [])
        if not rows:
            continue
        rows.sort(key=lambda row: int(row["stop_sequence"]))
        stops: list[StopTime] = []
        bad = False
        for row in rows:
            stop = stop_meta.get(row["stop_id"])
            if stop is None:
                bad = True
                break
            try:
                arrival_s = hms_to_seconds(row["arrival_time"])
                departure_s = hms_to_seconds(row["departure_time"])
                latitude = float(stop["stop_lat"])
                longitude = float(stop["stop_lon"])
            except (KeyError, TypeError, ValueError):
                bad = True
                break
            stops.append(
                StopTime(
                    stop_id=row["stop_id"],
                    stop_sequence=int(row["stop_sequence"]),
                    arrival_s=arrival_s,
                    departure_s=departure_s,
                    lat=latitude,
                    lon=longitude,
                    name=stop.get("stop_name", row["stop_id"]),
                )
            )
        if bad or not stops:
            skipped_bad_times += 1
            continue
        trip = Trip(
            trip_id=trip_id,
            route=meta["route"],
            operator_noc=meta["operator_noc"],
            operator_name=meta["operator_name"],
            service_id=meta["service_id"],
            headsign=meta["headsign"],
            vehicle_journey_code=meta["vehicle_journey_code"],
            stops=stops,
        )
        trips.append(trip)

    info: dict[str, object] = {
        "service_date": service_date.isoformat(),
        "relevant_trip_count": len(trips),
        "target_trip_count": sum(1 for trip in trips if trip.target(target_stop) is not None),
        "skipped_bad_time_trips": skipped_bad_times,
    }
    return trips, info


def xml_text(parent: ET.Element, path: str, default: str = "") -> str:
    element = parent.find(path, SIRI_NS)
    return element.text if element is not None and element.text is not None else default


def parse_iso_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def parse_siri(
    xml_bytes: bytes,
    selected_services: Iterable[ServiceSpec],
) -> tuple[list[LiveVehicle], datetime | None, list[str]]:
    selected = {(service.operator_noc, service.route) for service in selected_services}
    root = ET.fromstring(xml_bytes)
    response_text = xml_text(root, ".//s:VehicleMonitoringDelivery/s:ResponseTimestamp")
    response_dt = parse_iso_datetime(response_text)
    vehicles: list[LiveVehicle] = []
    warnings: list[str] = []

    for activity in root.findall(".//s:VehicleActivity", SIRI_NS):
        journey = activity.find("s:MonitoredVehicleJourney", SIRI_NS)
        if journey is None:
            continue
        route = xml_text(journey, "s:LineRef").strip()
        operator = xml_text(journey, "s:OperatorRef").strip()
        if (operator, route) not in selected:
            continue

        vehicle_ref = xml_text(journey, "s:VehicleRef")
        latitude = xml_text(journey, "s:VehicleLocation/s:Latitude").strip()
        longitude = xml_text(journey, "s:VehicleLocation/s:Longitude").strip()
        if not latitude or not longitude:
            warnings.append(f"{route} vehicle {vehicle_ref or '?'} missing GPS")
            continue

        origin = parse_iso_datetime(xml_text(journey, "s:OriginAimedDepartureTime"))
        destination = parse_iso_datetime(xml_text(journey, "s:DestinationAimedArrivalTime"))
        recorded = parse_iso_datetime(xml_text(activity, "s:RecordedAtTime"))
        if origin is None or destination is None or recorded is None:
            missing: list[str] = []
            if origin is None:
                missing.append("OriginAimedDepartureTime")
            if destination is None:
                missing.append("DestinationAimedArrivalTime")
            if recorded is None:
                missing.append("RecordedAtTime")
            warnings.append(
                f"{route} vehicle {vehicle_ref or '?'} missing/invalid {', '.join(missing)}"
            )
            continue

        try:
            latitude_f = float(latitude)
            longitude_f = float(longitude)
        except ValueError:
            warnings.append(f"{route} vehicle {vehicle_ref or '?'} invalid GPS")
            continue

        vehicles.append(
            LiveVehicle(
                route=route,
                operator_noc=operator,
                vehicle=vehicle_ref,
                dated_ref=xml_text(
                    journey, "s:FramedVehicleJourneyRef/s:DatedVehicleJourneyRef"
                ),
                origin_ref=xml_text(journey, "s:OriginRef"),
                destination_ref=xml_text(journey, "s:DestinationRef"),
                origin_dt=origin,
                destination_dt=destination,
                recorded_dt=recorded,
                lat=latitude_f,
                lon=longitude_f,
                block_ref=xml_text(journey, "s:BlockRef"),
                ticket_service=xml_text(
                    activity,
                    "s:Extensions/s:VehicleJourney/s:Operational/s:TicketMachine/"
                    "s:TicketMachineServiceCode",
                ),
                journey_code=xml_text(
                    activity,
                    "s:Extensions/s:VehicleJourney/s:Operational/s:TicketMachine/s:JourneyCode",
                ),
            )
        )

    return vehicles, response_dt, warnings


def static_signature(trip: Trip) -> tuple[str, str, str, str, str, str]:
    return (
        trip.operator_noc,
        trip.route,
        trip.origin.stop_id,
        trip.destination.stop_id,
        seconds_to_hms(trip.origin.departure_s),
        seconds_to_hms(trip.destination.arrival_s),
    )


def live_signature(vehicle: LiveVehicle) -> tuple[str, str, str, str, str, str]:
    return (
        vehicle.operator_noc,
        vehicle.route,
        vehicle.origin_ref,
        vehicle.destination_ref,
        vehicle.origin_dt.strftime("%H:%M:%S"),
        vehicle.destination_dt.strftime("%H:%M:%S"),
    )


def project_to_segment(
    lat: float, lon: float, point_a: StopTime, point_b: StopTime
) -> tuple[float, float]:
    """Return distance in metres from a segment and fraction along it."""
    earth = 6_371_000.0
    lat0 = math.radians(lat)

    def xy(stop: StopTime) -> tuple[float, float]:
        x = math.radians(stop.lon - lon) * earth * math.cos(lat0)
        y = math.radians(stop.lat - lat) * earth
        return x, y

    ax, ay = xy(point_a)
    bx, by = xy(point_b)
    vx, vy = bx - ax, by - ay
    denominator = vx * vx + vy * vy
    fraction = 0.0 if denominator == 0 else -(ax * vx + ay * vy) / denominator
    fraction = max(0.0, min(1.0, fraction))
    px = ax + fraction * vx
    py = ay + fraction * vy
    return math.hypot(px, py), fraction


def estimate_delay_and_progress(
    vehicle: LiveVehicle, trip: Trip, service_date: date
) -> tuple[float, float, float] | None:
    if len(trip.stops) < 2:
        return None

    options: list[tuple[float, float, int, float]] = []
    for index in range(len(trip.stops) - 1):
        distance, fraction = project_to_segment(
            vehicle.lat, vehicle.lon, trip.stops[index], trip.stops[index + 1]
        )
        point_a, point_b = trip.stops[index], trip.stops[index + 1]
        scheduled_s = point_a.departure_s + fraction * (
            point_b.arrival_s - point_a.departure_s
        )
        scheduled_dt = service_datetime(service_date, int(round(scheduled_s)))
        delay_minutes = (vehicle.recorded_dt - scheduled_dt).total_seconds() / 60.0
        if -20 <= delay_minutes <= 180:
            options.append((distance, fraction, index, delay_minutes))

    if not options:
        return None

    distance, fraction, index, delay_minutes = min(options, key=lambda item: item[0])
    return delay_minutes, index + fraction, distance


def fuzzy_match_trip(
    vehicle: LiveVehicle, trips: list[Trip], service_date: date
) -> tuple[Trip | None, str]:
    candidates: list[tuple[float, Trip]] = []
    for trip in trips:
        if trip.operator_noc != vehicle.operator_noc or trip.route != vehicle.route:
            continue
        if trip.origin.stop_id != vehicle.origin_ref:
            continue
        if trip.destination.stop_id != vehicle.destination_ref:
            continue
        origin_dt = service_datetime(service_date, trip.origin.departure_s)
        destination_dt = service_datetime(service_date, trip.destination.arrival_s)
        origin_diff = abs((origin_dt - vehicle.origin_dt).total_seconds())
        destination_diff = abs((destination_dt - vehicle.destination_dt).total_seconds())
        if origin_diff <= 180 and destination_diff <= 180:
            candidates.append((origin_diff + destination_diff, trip))

    if not candidates:
        return None, "unmatched"
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > 1 and abs(candidates[1][0] - candidates[0][0]) < 1:
        return None, "ambiguous"
    return candidates[0][1], "fuzzy"


def calculate_candidates(
    trips: list[Trip],
    vehicles: list[LiveVehicle],
    now: datetime,
    target_stop: str,
    max_live_age_seconds: int,
) -> tuple[list[Candidate], dict[str, int]]:
    service_date = now.astimezone(LOCAL_TZ).date()

    by_signature: dict[tuple[str, str, str, str, str, str], list[Trip]] = defaultdict(list)
    for trip in trips:
        by_signature[static_signature(trip)].append(trip)

    live_by_trip: dict[str, tuple[LiveVehicle, float, float, float]] = {}
    match_stats = {
        "matched_exact": 0,
        "matched_fuzzy": 0,
        "ambiguous": 0,
        "unmatched": 0,
        "stale": 0,
    }

    for vehicle in vehicles:
        age = (now - vehicle.recorded_dt).total_seconds()
        if age > max_live_age_seconds:
            match_stats["stale"] += 1
            continue

        matches = by_signature.get(live_signature(vehicle), [])
        trip: Trip | None = None
        if len(matches) == 1:
            trip = matches[0]
            match_stats["matched_exact"] += 1
        elif len(matches) > 1:
            match_stats["ambiguous"] += 1
            continue
        else:
            trip, kind = fuzzy_match_trip(vehicle, trips, service_date)
            if kind == "fuzzy":
                match_stats["matched_fuzzy"] += 1
            elif kind == "ambiguous":
                match_stats["ambiguous"] += 1
            else:
                match_stats["unmatched"] += 1
            if trip is None:
                continue

        progress = estimate_delay_and_progress(vehicle, trip, service_date)
        if progress is None:
            continue
        delay, route_progress, distance = progress
        live_by_trip[trip.trip_id] = (vehicle, delay, route_progress, distance)

    candidates: list[Candidate] = []
    for trip in trips:
        target = trip.target(target_stop)
        if target is None:
            continue
        target_index = trip.stops.index(target)
        target_is_origin = target_index == 0
        target_is_destination = target_index == len(trip.stops) - 1
        stop_role = (
            "origin"
            if target_is_origin
            else "destination"
            if target_is_destination
            else "intermediate"
        )
        scheduled_seconds = target.departure_s if target_is_origin else target.arrival_s
        scheduled = service_datetime(service_date, scheduled_seconds)
        expected = scheduled
        realtime = False
        vehicle_id: str | None = None
        delay: float | None = None
        raw_delay: float | None = None
        timing_status: str | None = None
        prediction_clamped = False
        last_update: datetime | None = None
        latitude: float | None = None
        longitude: float | None = None
        distance_to_route: float | None = None

        live = live_by_trip.get(trip.trip_id)
        if live:
            vehicle, delay_est, route_progress, distance = live
            if route_progress < target_index + 0.05:
                raw_delay = delay_est
                timing_status = (
                    "early"
                    if delay_est < -1.0
                    else "late"
                    if delay_est > 1.0
                    else "on_time"
                )
                predicted = scheduled + timedelta(minutes=delay_est)

                # A vehicle may arrive at the origin/terminus early, but a passenger
                # departure should never be predicted before the published timetable.
                # Keep the raw early-running estimate for diagnostics/status while
                # clamping the passenger-facing expected departure and effective delay.
                if target_is_origin and predicted < scheduled:
                    expected = scheduled
                    delay = 0.0
                    prediction_clamped = True
                else:
                    expected = predicted
                    delay = delay_est

                realtime = True
                vehicle_id = vehicle.vehicle
                last_update = vehicle.recorded_dt
                latitude = vehicle.lat
                longitude = vehicle.lon
                distance_to_route = distance
            else:
                continue

        if not realtime and scheduled < now - timedelta(seconds=45):
            continue
        if realtime and expected < now - timedelta(seconds=45):
            continue

        candidates.append(
            Candidate(
                service_key=make_service_key(trip.operator_noc, trip.route),
                operator_noc=trip.operator_noc,
                operator_name=trip.operator_name,
                route=trip.route,
                trip_id=trip.trip_id,
                destination=trip.headsign or trip.destination.name,
                scheduled=scheduled,
                expected=expected,
                realtime=realtime,
                vehicle=vehicle_id,
                delay_minutes=delay,
                raw_delay_minutes=raw_delay,
                timing_status=timing_status,
                stop_role=stop_role,
                prediction_clamped=prediction_clamped,
                last_update=last_update,
                latitude=latitude,
                longitude=longitude,
                position_to_route_m=distance_to_route,
            )
        )

    candidates.sort(key=lambda candidate: candidate.expected)
    return candidates, match_stats


def candidate_dict(
    candidate: Candidate | None,
    now: datetime,
    service: ServiceSpec | None = None,
) -> dict[str, object]:
    if candidate is None:
        return {
            "available": False,
            "service_key": service.key if service else None,
            "operator_noc": service.operator_noc if service else None,
            "route": service.route if service else None,
            "minutes": None,
            "scheduled": None,
            "expected": None,
            "realtime": False,
            "source": "none",
            "vehicle": None,
            "destination": None,
            "delay_minutes": None,
            "raw_delay_minutes": None,
            "timing_status": None,
            "stop_role": None,
            "prediction_clamped": False,
            "last_update": None,
            "latitude": None,
            "longitude": None,
            "position_to_route_m": None,
            "trip_id": None,
        }

    seconds = max(0.0, (candidate.expected - now).total_seconds())
    minutes = max(0, int(seconds // 60))
    return {
        "available": True,
        "service_key": candidate.service_key,
        "operator_noc": candidate.operator_noc,
        "operator_name": candidate.operator_name,
        "route": candidate.route,
        "minutes": minutes,
        "scheduled": candidate.scheduled.isoformat(),
        "expected": candidate.expected.isoformat(),
        "realtime": candidate.realtime,
        "source": "live" if candidate.realtime else "scheduled",
        "vehicle": candidate.vehicle,
        "destination": candidate.destination,
        "delay_minutes": (
            None if candidate.delay_minutes is None else round(candidate.delay_minutes, 1)
        ),
        "raw_delay_minutes": (
            None
            if candidate.raw_delay_minutes is None
            else round(candidate.raw_delay_minutes, 1)
        ),
        "timing_status": (
            candidate.timing_status if candidate.realtime else "timetable"
        ),
        "stop_role": candidate.stop_role,
        "prediction_clamped": candidate.prediction_clamped,
        "last_update": (
            None if candidate.last_update is None else candidate.last_update.isoformat()
        ),
        "latitude": None if candidate.latitude is None else round(candidate.latitude, 6),
        "longitude": None if candidate.longitude is None else round(candidate.longitude, 6),
        "position_to_route_m": (
            None
            if candidate.position_to_route_m is None
            else round(candidate.position_to_route_m)
        ),
        "trip_id": candidate.trip_id,
    }


def make_snapshot(
    trips: list[Trip],
    gtfs_info: dict[str, object],
    vehicles: list[LiveVehicle],
    now: datetime,
    target_stop: str,
    stop_name: str,
    services: list[ServiceSpec],
    route_errors: dict[str, str],
    parse_warnings: list[str],
    max_live_age_seconds: int,
) -> dict[str, object]:
    candidates, match_stats = calculate_candidates(
        trips,
        vehicles,
        now,
        target_stop=target_stop,
        max_live_age_seconds=max_live_age_seconds,
    )

    per_service: dict[str, dict[str, object]] = {}
    for service in services:
        first = next(
            (candidate for candidate in candidates if candidate.service_key == service.key),
            None,
        )
        per_service[service.key] = candidate_dict(first, now, service)

    if not route_errors:
        health = "ok"
    elif len(route_errors) < len(services):
        health = "degraded"
    else:
        health = "scheduled_only"

    matched = match_stats["matched_exact"] + match_stats["matched_fuzzy"]
    departure_list = [candidate_dict(candidate, now) for candidate in candidates[:12]]
    return {
        "generated_at": now.isoformat(),
        "stop": {"atco": target_stop, "name": stop_name},
        "next_bus": candidate_dict(candidates[0] if candidates else None, now),
        "services": per_service,
        "departures": departure_list,
        "health": health,
        "live_vehicle_count": len(vehicles),
        "match_stats": {**match_stats, "matched": matched},
        "api_errors": route_errors,
        "parse_warnings": parse_warnings[-20:],
        "gtfs": gtfs_info,
    }
