"""Walking-time guidance tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.walking import apply_walking_guidance

TZ = ZoneInfo("Europe/London")


def _snapshot(expected: str = "2026-08-26T10:30:00+01:00") -> dict:
    return {
        "next_bus": {
            "available": True,
            "route": "T1",
            "expected": expected,
        }
    }


def test_walking_guidance_disabled_at_zero() -> None:
    now = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)
    data = apply_walking_guidance(_snapshot(), now, 0)["next_bus"]
    assert data["walking_minutes"] == 0
    assert data["leave_by"] is None
    assert data["leave_in_minutes"] is None
    assert data["leave_now"] is False


def test_leave_by_and_leave_in_are_calculated() -> None:
    now = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)
    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]
    assert data["leave_by"] == "2026-08-26T10:20:00+01:00"
    assert data["leave_in_minutes"] == 20
    assert data["leave_now"] is False


def test_leave_now_turns_on_after_leave_by() -> None:
    now = datetime(2026, 8, 26, 10, 21, tzinfo=TZ)
    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]
    assert data["leave_in_minutes"] == 0
    assert data["leave_now"] is True


def test_leave_now_turns_off_after_expected_bus_time() -> None:
    now = datetime(2026, 8, 26, 10, 31, tzinfo=TZ)
    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]
    assert data["leave_by"] == "2026-08-26T10:20:00+01:00"
    assert data["leave_in_minutes"] is None
    assert data["leave_now"] is False


def test_fractional_minute_rounds_up_before_leave_time() -> None:
    now = datetime(2026, 8, 26, 10, 19, 30, tzinfo=TZ)
    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]
    assert data["leave_in_minutes"] == 1
    assert data["leave_now"] is False


def test_unavailable_next_bus_has_no_leave_guidance() -> None:
    now = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)
    snapshot = _snapshot()
    snapshot["next_bus"]["available"] = False
    data = apply_walking_guidance(snapshot, now, 10)["next_bus"]
    assert data["walking_minutes"] == 10
    assert data["leave_by"] is None
    assert data["leave_in_minutes"] is None
    assert data["leave_now"] is False
