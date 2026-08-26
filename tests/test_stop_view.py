"""Regression tests for arrivals/departures/terminus post-processing."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.api import LiveVehicle, ServiceSpec, StopTime, Trip
from custom_components.bods_bus_tracker.stop_view import apply_stop_view

TZ = ZoneInfo("Europe/London")


def _snapshot(stop_id: str, name: str) -> dict:
    return {
        "stop": {"atco": stop_id, "name": name},
        "next_bus": {},
        "services": {},
        "departures": [],
    }


def _intermediate_trip() -> Trip:
    return Trip(
        trip_id="through-1",
        route="T1",
        operator_noc="TEST",
        operator_name="Test Operator",
        service_id="svc",
        headsign="Destination",
        vehicle_journey_code="1",
        stops=[
            StopTime("A", 1, 36000, 36000, 55.000, -1.000, "Origin"),
            StopTime("M", 2, 36600, 36600, 55.050, -1.000, "Middle Stop"),
            StopTime("B", 3, 37200, 37200, 55.100, -1.000, "Destination"),
        ],
    )


def _inbound_trip() -> Trip:
    return Trip(
        trip_id="inbound-1",
        route="T1",
        operator_noc="TEST",
        operator_name="Test Operator",
        service_id="svc",
        headsign="Terminus",
        vehicle_journey_code="10",
        stops=[
            StopTime("A", 1, 41400, 41400, 55.000, -1.000, "Origin Town"),
            StopTime("T", 2, 43200, 43200, 55.100, -1.100, "Terminus"),
        ],
    )


def _outbound_trip() -> Trip:
    return Trip(
        trip_id="outbound-1",
        route="T1",
        operator_noc="TEST",
        operator_name="Test Operator",
        service_id="svc",
        headsign="Outbound Town",
        vehicle_journey_code="20",
        stops=[
            StopTime("T", 1, 43800, 43800, 55.100, -1.100, "Terminus"),
            StopTime("B", 2, 45600, 45600, 55.200, -1.200, "Outbound Town"),
        ],
    )


def _vehicle_for(
    trip: Trip,
    vehicle: str,
    recorded: datetime,
    lat: float,
    lon: float,
) -> LiveVehicle:
    service_date = recorded.date()
    midnight = datetime.combine(service_date, datetime.min.time(), tzinfo=TZ)
    return LiveVehicle(
        route=trip.route,
        operator_noc=trip.operator_noc,
        vehicle=vehicle,
        dated_ref=trip.trip_id,
        origin_ref=trip.origin.stop_id,
        destination_ref=trip.destination.stop_id,
        origin_dt=midnight + timedelta(seconds=trip.origin.departure_s),
        destination_dt=midnight + timedelta(seconds=trip.destination.arrival_s),
        recorded_dt=recorded,
        lat=lat,
        lon=lon,
        block_ref="",
        ticket_service=trip.route,
        journey_code=trip.vehicle_journey_code,
    )


def test_intermediate_departures_preserves_existing_boarding_view() -> None:
    now = datetime(2026, 8, 26, 10, 5, tzinfo=TZ)
    trip = _intermediate_trip()
    result = apply_stop_view(
        _snapshot("M", "Middle Stop"),
        [trip],
        [],
        now,
        "M",
        [ServiceSpec("TEST", "T1")],
        "departures",
        180,
    )

    assert result["stop"]["profile"] == "intermediate"
    assert result["next_bus"]["trip_id"] == "through-1"
    assert result["next_bus"]["stop_role"] == "intermediate"
    assert result["next_bus"]["event_type"] == "call"
    assert len(result["departures"]) == 1
    assert len(result["arrivals"]) == 1


def test_terminus_both_separates_arrival_from_proven_outbound_at_stand() -> None:
    now = datetime(2026, 8, 26, 11, 59, 10, tzinfo=TZ)
    inbound = _inbound_trip()
    outbound = _outbound_trip()
    incoming_vehicle = _vehicle_for(
        inbound,
        "IN100",
        datetime(2026, 8, 26, 11, 59, tzinfo=TZ),
        55.100,
        -1.100,
    )
    outbound_vehicle = _vehicle_for(
        outbound,
        "OUT200",
        datetime(2026, 8, 26, 11, 59, tzinfo=TZ),
        55.100,
        -1.100,
    )

    result = apply_stop_view(
        _snapshot("T", "Terminus"),
        [inbound, outbound],
        [incoming_vehicle, outbound_vehicle],
        now,
        "T",
        [ServiceSpec("TEST", "T1")],
        "both",
        180,
    )

    assert result["stop"]["profile"] == "terminus"
    assert result["stop"]["combined_supported"] is True

    # In BOTH mode passenger-facing Next bus remains a boardable departure.
    assert result["next_bus"]["trip_id"] == "outbound-1"
    assert result["next_departure"]["trip_id"] == "outbound-1"
    assert result["next_arrival"]["trip_id"] == "inbound-1"

    assert result["departures"][0]["event_type"] == "departure"
    assert result["arrivals"][0]["event_type"] == "arrival"

    at_stand = result["terminus"]["at_stand_departures"]
    arrived = result["terminus"]["arrived_vehicles"]
    assert [row["vehicle"] for row in at_stand] == ["OUT200"]
    assert [row["vehicle"] for row in arrived] == ["IN100"]

    # Crucially, the incoming vehicle is not inferred to form the outbound journey.
    assert at_stand[0]["vehicle"] != arrived[0]["vehicle"]
    assert "never assumed" in result["terminus"]["linking_policy"]


def test_arrivals_mode_selects_incoming_journey() -> None:
    now = datetime(2026, 8, 26, 11, 59, 10, tzinfo=TZ)
    inbound = _inbound_trip()
    outbound = _outbound_trip()
    result = apply_stop_view(
        _snapshot("T", "Terminus"),
        [inbound, outbound],
        [],
        now,
        "T",
        [ServiceSpec("TEST", "T1")],
        "arrivals",
        180,
    )

    assert result["next_bus"]["trip_id"] == "inbound-1"
    assert result["next_bus"]["stop_role"] == "destination"
    assert result["next_departure"]["trip_id"] == "outbound-1"
