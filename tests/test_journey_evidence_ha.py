"""Tests for the read-only Home Assistant journey-location adapter."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.core import State

from custom_components.bods_bus_tracker.journey_evidence_ha import (
    location_fix_from_state,
)

TZ = ZoneInfo("Europe/London")


def test_location_fix_from_state_reads_only_location_attributes() -> None:
    observed = datetime(2026, 9, 14, 15, 0, tzinfo=TZ)
    state = State(
        "person.example",
        "not_home",
        {
            "latitude": 55.0,
            "longitude": -1.0,
            "gps_accuracy": 12,
        },
        last_changed=observed,
        last_reported=observed,
        last_updated=observed,
    )

    fix = location_fix_from_state(state)

    assert fix is not None
    assert fix.latitude == 55.0
    assert fix.longitude == -1.0
    assert fix.accuracy_m == 12
    assert fix.observed_at == observed


def test_location_fix_rejects_missing_or_invalid_coordinates() -> None:
    assert location_fix_from_state(None) is None
    assert (
        location_fix_from_state(
            State("person.example", "not_home", {"latitude": 55.0})
        )
        is None
    )
    assert (
        location_fix_from_state(
            State(
                "person.example",
                "not_home",
                {"latitude": 91.0, "longitude": -1.0},
            )
        )
        is None
    )
    assert (
        location_fix_from_state(
            State(
                "person.example",
                "not_home",
                {"latitude": float("nan"), "longitude": -1.0},
            )
        )
        is None
    )


def test_invalid_accuracy_is_treated_as_unknown_not_location_failure() -> None:
    state = State(
        "person.example",
        "not_home",
        {
            "latitude": 55.0,
            "longitude": -1.0,
            "gps_accuracy": -1,
        },
    )

    fix = location_fix_from_state(state)

    assert fix is not None
    assert fix.accuracy_m is None
