"""Diagnostics privacy-policy tests."""

from __future__ import annotations

from custom_components.bods_bus_tracker.diagnostics import _strip_coordinates


def test_diagnostics_strip_coordinates_and_private_guidance_state() -> None:
    payload = {
        "keep": "value",
        "latitude": 55.1,
        "longitude": -1.6,
        "_departures_for_guidance": [
            {
                "route": "X18",
                "latitude": 55.2,
                "longitude": -1.7,
                "trip_id": "private-working-detail",
            }
        ],
        "nested": {
            "latitude": 55.3,
            "longitude": -1.8,
            "keep": 123,
        },
    }

    assert _strip_coordinates(payload) == {
        "keep": "value",
        "nested": {"keep": 123},
    }
