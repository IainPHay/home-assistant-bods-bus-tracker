"""Catchable-bus guidance tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.catchable import apply_catchable_guidance

TZ = ZoneInfo("Europe/London")


def _row(
    route: str,
    expected: str,
    *,
    scheduled: str | None = None,
    source: str = "scheduled",
    latitude: float | None = 55.1,
    longitude: float | None = -1.6,
) -> dict:
    return {
        "route": route,
        "operator": "Arriva North East",
        "operator_noc": "ANUM",
        "service_key": f"ANUM|{route}",
        "destination": "Newcastle",
        "minutes": 10,
        "scheduled": scheduled or expected,
        "expected": expected,
        "source": source,
        "realtime": source == "live",
        "timing_status": "timetable" if source != "live" else "late",
        "delay_minutes": None if source != "live" else 5.0,
        "vehicle": "1234" if source == "live" else None,
        "latitude": latitude,
        "longitude": longitude,
        "trip_id": "private-detail-not-needed",
    }


def _snapshot(*rows: dict) -> dict:
    return {"departures": list(rows)}


def test_first_reachable_departure_is_selected() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(
            _row("X14", "2026-09-13T10:05:00+01:00"),
            _row("X15", "2026-09-13T10:09:00+01:00"),
            _row("X18", "2026-09-13T10:20:00+01:00"),
        ),
        now,
        walking_minutes=8,
    )["catchable"]

    assert data["status"] == "ok"
    assert data["required_lead_minutes"] == 8
    assert data["departure"]["route"] == "X15"
    assert data["following_departure"]["route"] == "X18"


def test_margin_is_added_to_required_lead_time() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(
            _row("X15", "2026-09-13T10:09:00+01:00"),
            _row("X18", "2026-09-13T10:12:00+01:00"),
        ),
        now,
        walking_minutes=8,
        margin_minutes=2,
    )["catchable"]

    assert data["margin_minutes"] == 2
    assert data["required_lead_minutes"] == 10
    assert data["departure"]["route"] == "X18"


def test_exact_threshold_is_catchable() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(_row("X14", "2026-09-13T10:10:00+01:00")),
        now,
        walking_minutes=8,
        margin_minutes=2,
    )["catchable"]

    assert data["status"] == "ok"
    assert data["departure"]["route"] == "X14"


def test_live_delay_can_make_a_bus_catchable() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(
            _row(
                "X14",
                "2026-09-13T10:12:00+01:00",
                scheduled="2026-09-13T10:05:00+01:00",
                source="live",
            ),
            _row("X15", "2026-09-13T10:20:00+01:00"),
        ),
        now,
        walking_minutes=10,
    )["catchable"]

    assert data["departure"]["route"] == "X14"
    assert data["departure"]["source"] == "live"
    assert data["departure"]["scheduled"] == "2026-09-13T10:05:00+01:00"
    assert data["departure"]["expected"] == "2026-09-13T10:12:00+01:00"


def test_no_walking_time_disables_catchable_state() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(_row("X14", "2026-09-13T10:10:00+01:00")),
        now,
        walking_minutes=0,
    )["catchable"]

    assert data["status"] == "walking_disabled"
    assert data["departure"] is None


def test_empty_departures_are_reported() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(),
        now,
        walking_minutes=5,
    )["catchable"]

    assert data["status"] == "no_departures"


def test_none_in_visible_window_is_reported() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(
            _row("X14", "2026-09-13T10:03:00+01:00"),
            _row("X15", "2026-09-13T10:04:00+01:00"),
        ),
        now,
        walking_minutes=10,
    )["catchable"]

    assert data["status"] == "none_in_window"
    assert data["departure"] is None


def test_invalid_expected_falls_back_to_scheduled() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    row = _row(
        "X14",
        "not-a-time",
        scheduled="2026-09-13T10:15:00+01:00",
    )
    data = apply_catchable_guidance(
        _snapshot(row),
        now,
        walking_minutes=10,
    )["catchable"]

    assert data["status"] == "ok"
    assert data["departure"]["route"] == "X14"


def test_summary_does_not_copy_vehicle_coordinates() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    data = apply_catchable_guidance(
        _snapshot(_row("X14", "2026-09-13T10:15:00+01:00", source="live")),
        now,
        walking_minutes=5,
    )["catchable"]

    departure = data["departure"]
    assert "latitude" not in departure
    assert "longitude" not in departure
    assert "trip_id" not in departure
    assert departure["vehicle"] == "1234"


def test_private_full_departure_sequence_is_used_and_removed() -> None:
    now = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    early_rows = [
        _row(f"E{index}", f"2026-09-13T10:{index + 1:02d}:00+01:00")
        for index in range(12)
    ]
    catchable = _row("LATE", "2026-09-13T10:20:00+01:00")
    snapshot = {
        "departures": early_rows,
        "_departures_for_guidance": [*early_rows, catchable],
    }

    result = apply_catchable_guidance(
        snapshot,
        now,
        walking_minutes=15,
    )

    assert result["catchable"]["departure"]["route"] == "LATE"
    assert "_departures_for_guidance" not in result
