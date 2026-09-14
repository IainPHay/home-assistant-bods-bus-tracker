"""Synthetic end-to-end tests for the pure BODS/GTFS engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

import pytest

from custom_components.bods_bus_tracker.api import (
    LiveVehicle,
    _calling_trip_ids_for_stop,
    ServiceSpec,
    StopTime,
    Trip,
    active_services_for_date,
    build_gtfs_index,
    candidate_dict,
    discover_stop_services,
    estimate_delay_and_progress,
    fuzzy_match_trip,
    hms_to_seconds,
    is_probable_stop_code,
    live_signature,
    make_service_key,
    make_snapshot,
    parse_iso_datetime,
    parse_service_key,
    parse_siri,
    project_to_segment,
    search_stops,
    seconds_to_hms,
    service_datetime,
    static_signature,
    validate_gtfs,
)

TZ = ZoneInfo("Europe/London")
DAY = date(2026, 9, 11)


def _write_gtfs(path: Path) -> Path:
    """Build a small but structurally real regional GTFS archive."""
    files = {
        "agency.txt": """agency_id,agency_name,agency_noc
A1,Arriva Northumbria,ANUM
A2,Other Operator,OTHER
""",
        "routes.txt": """route_id,agency_id,route_short_name
R14,A1,X14
R18,A1,X18
RO,A2,O1
""",
        "trips.txt": """route_id,service_id,trip_id,trip_headsign,vehicle_journey_code
R14,WK,T14,Newcastle,1401
R18,WK,T18,Newcastle,1801
R14,ADD,TADD,Added Journey,1402
R14,WK,TBAD,Bad Journey,1403
RO,WK,TO,Other,1
""",
        "stops.txt": """stop_id,stop_code,stop_name,stop_lat,stop_lon
A,a-code,Origin,55.000,-1.000
B,b-code,The Fairway,55.050,-1.000
C,c-code,Destination,55.100,-1.000
BAD,bad-code,Bad Coords,not-a-lat,-1.200
""",
        "stop_times.txt": """trip_id,arrival_time,departure_time,stop_id,stop_sequence
T14,10:00:00,10:00:00,A,1
T14,10:10:00,10:10:00,B,2
T14,10:20:00,10:20:00,C,3
T18,11:00:00,11:00:00,A,1
T18,11:10:00,11:10:00,B,2
T18,11:20:00,11:20:00,C,3
TADD,12:00:00,12:00:00,A,1
TADD,12:10:00,12:10:00,B,2
TADD,12:20:00,12:20:00,C,3
TBAD,13:00:00,13:00:00,A,1
TBAD,not-a-time,13:10:00,B,2
TBAD,13:20:00,13:20:00,C,3
TO,10:00:00,10:00:00,A,1
TO,10:10:00,10:10:00,B,2
""",
        "calendar.txt": """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
WK,1,1,1,1,1,0,0,20260101,20261231
ADD,0,0,0,0,0,0,0,20260101,20261231
""",
        "calendar_dates.txt": """service_id,date,exception_type
ADD,20260911,1
WK,20260912,2
""",
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    return path


@pytest.fixture
def gtfs(tmp_path: Path) -> Path:
    return _write_gtfs(tmp_path / "region.zip")


def test_service_key_and_time_helpers() -> None:
    """Service IDs and GTFS time conversion are deterministic."""
    assert make_service_key("ANUM", "X14") == "ANUM|X14"
    assert parse_service_key(" ANUM | X14 ") == ServiceSpec("ANUM", "X14")
    with pytest.raises(ValueError):
        parse_service_key("broken")

    assert hms_to_seconds("25:01:02") == 90062
    with pytest.raises(ValueError):
        hms_to_seconds("10:30")
    assert seconds_to_hms(90062) == "01:01:02"
    assert service_datetime(DAY, 36000).hour == 10

    assert is_probable_stop_code("3100Z199842") is True
    assert is_probable_stop_code("The Fairway") is False


def test_validate_and_search_gtfs(gtfs: Path, tmp_path: Path) -> None:
    """GTFS validation and stop search cover exact, name and distance searches."""
    validate_gtfs(gtfs)
    validate_gtfs(gtfs, "B")
    with pytest.raises(ValueError):
        validate_gtfs(gtfs, "MISSING")

    invalid = tmp_path / "not.zip"
    invalid.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_gtfs(invalid)

    exact = search_stops(gtfs, "b-code", home_lat=55.0, home_lon=-1.0)
    assert exact[0].stop_id == "B"
    assert exact[0].distance_km is not None

    by_name = search_stops(gtfs, "Fairway")
    assert by_name[0].stop_name == "The Fairway"

    assert search_stops(gtfs, "") == ()
    assert all(result.stop_id != "BAD" for result in search_stops(gtfs, "Bad"))


def test_calling_trip_ids_for_stop_prefilters_raw_gtfs_lines() -> None:
    """Fast stop filtering preserves exact CSV column matching."""
    payload = b"""trip_id,arrival_time,departure_time,stop_id,stop_sequence
T1,10:00:00,10:00:00,3100Z199842,1
T2,10:05:00,10:05:00,OTHER,2
3100Z199842_TRIP,10:10:00,10:10:00,OTHER,3
T3,10:15:00,10:15:00,"3100Z199842",4
UNKNOWN,10:20:00,10:20:00,3100Z199842,5
"""

    matches = _calling_trip_ids_for_stop(
        BytesIO(payload),
        "3100Z199842",
        {"T1", "T2", "T3"},
    )

    assert matches == {"T1", "T3"}

    missing_columns = BytesIO(b"trip_id,arrival_time\nT1,10:00:00\n")
    assert _calling_trip_ids_for_stop(
        missing_columns,
        "3100Z199842",
        {"T1"},
    ) == set()


def test_discover_services_and_calendars(gtfs: Path) -> None:
    """Stop discovery joins agency/route/trip/stop data and honours calendars."""
    discovery = discover_stop_services(gtfs, "B")
    assert discovery.stop_name == "The Fairway"
    assert {(item.operator_noc, item.route) for item in discovery.services} == {
        ("ANUM", "X14"),
        ("ANUM", "X18"),
        ("OTHER", "O1"),
    }
    x14 = next(item for item in discovery.services if item.route == "X14")
    assert "Newcastle" in x14.headsigns

    with pytest.raises(LookupError):
        discover_stop_services(gtfs, "MISSING")

    with zipfile.ZipFile(gtfs) as zf:
        active = active_services_for_date(zf, DAY)
        assert {"WK", "ADD"} <= active

        saturday = active_services_for_date(zf, date(2026, 9, 12))
        assert "WK" not in saturday


def test_build_gtfs_index(gtfs: Path) -> None:
    """Day-specific index keeps selected active trips and skips malformed times."""
    trips, info = build_gtfs_index(
        gtfs,
        DAY,
        "B",
        [ServiceSpec("ANUM", "X14"), ServiceSpec("ANUM", "X18")],
    )

    assert {trip.trip_id for trip in trips} == {"T14", "T18", "TADD"}
    assert info["target_trip_count"] == 3
    assert info["skipped_bad_time_trips"] == 1

    t14 = next(trip for trip in trips if trip.trip_id == "T14")
    assert t14.origin.name == "Origin"
    assert t14.destination.name == "Destination"
    assert t14.target("B").stop_sequence == 2


def _siri(*activities: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Siri xmlns="http://www.siri.org.uk/siri">
  <ServiceDelivery>
    <VehicleMonitoringDelivery>
      <ResponseTimestamp>2026-09-11T10:05:00+01:00</ResponseTimestamp>
      {"".join(activities)}
    </VehicleMonitoringDelivery>
  </ServiceDelivery>
</Siri>
""".encode()


def _activity(
    *,
    route: str = "X14",
    operator: str = "ANUM",
    vehicle: str = "100",
    lat: str = "55.050",
    lon: str = "-1.000",
    origin: str = "2026-09-11T10:00:00+01:00",
    destination: str = "2026-09-11T10:20:00+01:00",
    recorded: str = "2026-09-11T10:05:00+01:00",
) -> str:
    return f"""
<VehicleActivity>
  <RecordedAtTime>{recorded}</RecordedAtTime>
  <MonitoredVehicleJourney>
    <LineRef>{route}</LineRef>
    <OperatorRef>{operator}</OperatorRef>
    <VehicleRef>{vehicle}</VehicleRef>
    <VehicleLocation><Latitude>{lat}</Latitude><Longitude>{lon}</Longitude></VehicleLocation>
    <OriginRef>A</OriginRef>
    <DestinationRef>C</DestinationRef>
    <OriginAimedDepartureTime>{origin}</OriginAimedDepartureTime>
    <DestinationAimedArrivalTime>{destination}</DestinationAimedArrivalTime>
    <FramedVehicleJourneyRef><DatedVehicleJourneyRef>T14</DatedVehicleJourneyRef></FramedVehicleJourneyRef>
    <BlockRef>block-1</BlockRef>
  </MonitoredVehicleJourney>
  <Extensions>
    <VehicleJourney>
      <Operational><TicketMachine>
        <TicketMachineServiceCode>X14</TicketMachineServiceCode>
        <JourneyCode>1401</JourneyCode>
      </TicketMachine></Operational>
    </VehicleJourney>
  </Extensions>
</VehicleActivity>
"""


def test_parse_siri_valid_and_warning_paths() -> None:
    """SIRI parser accepts selected valid vehicles and ignores malformed records."""
    xml = _siri(
        "<VehicleActivity><RecordedAtTime>2026-09-11T10:00:00+01:00</RecordedAtTime></VehicleActivity>",
        _activity(route="NOT_SELECTED", vehicle="skip"),
        _activity(vehicle="nogps", lat="", lon=""),
        _activity(vehicle="baddate", origin="not-a-date"),
        _activity(vehicle="badgps", lat="not-a-number"),
        _activity(vehicle="good"),
    )

    vehicles, response_dt, warnings = parse_siri(
        xml,
        [ServiceSpec("ANUM", "X14")],
    )

    assert response_dt == datetime(2026, 9, 11, 10, 5, tzinfo=TZ)
    assert [vehicle.vehicle for vehicle in vehicles] == ["good"]
    assert vehicles[0].ticket_service == "X14"
    assert vehicles[0].journey_code == "1401"
    assert any("missing GPS" in warning for warning in warnings)
    assert any("OriginAimedDepartureTime" in warning for warning in warnings)
    assert any("invalid GPS" in warning for warning in warnings)

    assert parse_iso_datetime("") is None
    assert parse_iso_datetime("bad") is None


def _trip(trip_id: str = "T14", offset: int = 0) -> Trip:
    return Trip(
        trip_id=trip_id,
        route="X14",
        operator_noc="ANUM",
        operator_name="Arriva Northumbria",
        service_id="WK",
        headsign="Newcastle",
        vehicle_journey_code="1401",
        stops=[
            StopTime("A", 1, 36000 + offset, 36000 + offset, 55.0, -1.0, "Origin"),
            StopTime("B", 2, 36600 + offset, 36600 + offset, 55.05, -1.0, "The Fairway"),
            StopTime("C", 3, 37200 + offset, 37200 + offset, 55.10, -1.0, "Destination"),
        ],
    )


def _vehicle(
    *,
    origin_shift: int = 0,
    recorded: datetime | None = None,
) -> LiveVehicle:
    return LiveVehicle(
        route="X14",
        operator_noc="ANUM",
        vehicle="100",
        dated_ref="T14",
        origin_ref="A",
        destination_ref="C",
        origin_dt=datetime(2026, 9, 11, 10, 0, tzinfo=TZ)
        + timedelta(seconds=origin_shift),
        destination_dt=datetime(2026, 9, 11, 10, 20, tzinfo=TZ)
        + timedelta(seconds=origin_shift),
        recorded_dt=recorded or datetime(2026, 9, 11, 10, 5, tzinfo=TZ),
        lat=55.025,
        lon=-1.0,
        block_ref="block",
        ticket_service="X14",
        journey_code="1401",
    )


def test_matching_geometry_and_signatures() -> None:
    """Geometric progress and exact/fuzzy signatures behave predictably."""
    trip = _trip()
    vehicle = _vehicle()

    assert static_signature(trip) == live_signature(vehicle)

    distance, fraction = project_to_segment(
        55.025,
        -1.0,
        trip.stops[0],
        trip.stops[1],
    )
    assert distance < 50
    assert 0.45 < fraction < 0.55

    progress = estimate_delay_and_progress(vehicle, trip, DAY)
    assert progress is not None

    one_stop = Trip(
        trip_id="one",
        route="X14",
        operator_noc="ANUM",
        operator_name="Arriva",
        service_id="WK",
        headsign="",
        vehicle_journey_code="",
        stops=[StopTime("A", 1, 36000, 36000, 55.0, -1.0, "Only")],
    )
    assert estimate_delay_and_progress(vehicle, one_stop, DAY) is None


def test_fuzzy_matching_outcomes() -> None:
    """Fuzzy matching distinguishes match, no-match and ambiguity."""
    trip = _trip()
    fuzzy_vehicle = _vehicle(origin_shift=60)

    matched, kind = fuzzy_match_trip(fuzzy_vehicle, [trip], DAY)
    assert matched is trip
    assert kind == "fuzzy"

    unmatched, kind = fuzzy_match_trip(
        replace(fuzzy_vehicle, route="X99"),
        [trip],
        DAY,
    )
    assert unmatched is None
    assert kind == "unmatched"

    duplicate = _trip("T14-duplicate")
    ambiguous, kind = fuzzy_match_trip(fuzzy_vehicle, [trip, duplicate], DAY)
    assert ambiguous is None
    assert kind == "ambiguous"


def test_snapshot_health_and_empty_candidate() -> None:
    """Snapshot health reports live API quality while timetable remains available."""
    now = datetime(2026, 9, 11, 9, 55, tzinfo=TZ)
    services = [ServiceSpec("ANUM", "X14"), ServiceSpec("ANUM", "X18")]
    trips = [_trip()]

    empty = candidate_dict(None, now, services[0])
    assert empty["available"] is False
    assert empty["route"] == "X14"

    ok = make_snapshot(
        trips,
        {},
        [],
        now,
        "B",
        "The Fairway",
        services,
        {},
        [],
        180,
    )
    assert ok["health"] == "ok"
    assert ok["next_bus"]["available"] is True
    assert ok["stop"] == {
        "atco": "B",
        "name": "The Fairway",
        "latitude": 55.05,
        "longitude": -1.0,
    }

    no_gtfs_stop = make_snapshot(
        [],
        {},
        [],
        now,
        "B",
        "The Fairway",
        services,
        {},
        [],
        180,
    )
    assert no_gtfs_stop["stop"] == {"atco": "B", "name": "The Fairway"}

    degraded = make_snapshot(
        trips,
        {},
        [],
        now,
        "B",
        "The Fairway",
        services,
        {"ANUM|X18": "timeout"},
        ["warning"],
        180,
    )
    assert degraded["health"] == "degraded"

    scheduled_only = make_snapshot(
        trips,
        {},
        [],
        now,
        "B",
        "The Fairway",
        services,
        {"ANUM|X14": "timeout", "ANUM|X18": "timeout"},
        [],
        180,
    )
    assert scheduled_only["health"] == "scheduled_only"
