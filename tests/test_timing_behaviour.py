"""Pure ETA timing-behaviour tests for 0.3.1."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.api import (
    LiveVehicle,
    ServiceSpec,
    StopTime,
    Trip,
    calculate_candidates,
    candidate_dict,
)

TZ = ZoneInfo("Europe/London")
SERVICE_DATE = date(2026, 8, 25)


def _trip() -> Trip:
    return Trip(
        trip_id="trip-1",
        route="T1",
        operator_noc="TEST",
        operator_name="Test Operator",
        service_id="svc",
        headsign="Town Centre",
        vehicle_journey_code="1",
        stops=[
            StopTime("A", 1, 36000, 36000, 55.0, -1.0, "Origin"),
            StopTime("B", 2, 36600, 36600, 55.1, -1.0, "Intermediate"),
            StopTime("C", 3, 37200, 37200, 55.2, -1.0, "Destination"),
        ],
    )


def _early_vehicle() -> LiveVehicle:
    return LiveVehicle(
        route="T1",
        operator_noc="TEST",
        vehicle="100",
        dated_ref="1",
        origin_ref="A",
        destination_ref="C",
        origin_dt=datetime(2026, 8, 25, 10, 0, tzinfo=TZ),
        destination_dt=datetime(2026, 8, 25, 10, 20, tzinfo=TZ),
        recorded_dt=datetime(2026, 8, 25, 9, 55, tzinfo=TZ),
        lat=55.0,
        lon=-1.0,
        block_ref="1",
        ticket_service="T1",
        journey_code="1",
    )


def test_origin_early_prediction_is_clamped() -> None:
    now = datetime(2026, 8, 25, 9, 54, tzinfo=TZ)
    candidates, _stats = calculate_candidates([_trip()], [_early_vehicle()], now, "A", 180)
    assert len(candidates) == 1
    data = candidate_dict(candidates[0], now, ServiceSpec("TEST", "T1"))
    assert data["expected"] == "2026-08-25T10:00:00+01:00"
    assert data["scheduled"] == "2026-08-25T10:00:00+01:00"
    assert data["delay_minutes"] == 0.0
    assert data["raw_delay_minutes"] == -5.0
    assert data["timing_status"] == "early"
    assert data["stop_role"] == "origin"
    assert data["prediction_clamped"] is True


def test_intermediate_early_prediction_is_preserved() -> None:
    now = datetime(2026, 8, 25, 9, 54, tzinfo=TZ)
    candidates, _stats = calculate_candidates([_trip()], [_early_vehicle()], now, "B", 180)
    assert len(candidates) == 1
    data = candidate_dict(candidates[0], now, ServiceSpec("TEST", "T1"))
    assert data["expected"] == "2026-08-25T10:05:00+01:00"
    assert data["scheduled"] == "2026-08-25T10:10:00+01:00"
    assert data["delay_minutes"] == -5.0
    assert data["raw_delay_minutes"] == -5.0
    assert data["timing_status"] == "early"
    assert data["stop_role"] == "intermediate"
    assert data["prediction_clamped"] is False
