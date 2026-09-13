"""Catchable-departure guidance for BODS Bus Tracker.

This module is deliberately downstream of ETA/matching. It only interprets the
already-selected departure rows plus the effective walking time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def _parse_departure_time(row: dict[str, Any]) -> datetime | None:
    """Return the best passenger-facing departure time for a row."""
    for key in ("expected", "scheduled"):
        value = row.get(key)
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            continue
    return None


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    """Return a privacy-safe, automation-friendly subset of a departure row."""
    keys = (
        "route",
        "operator",
        "operator_noc",
        "service_key",
        "destination",
        "minutes",
        "scheduled",
        "expected",
        "source",
        "realtime",
        "timing_status",
        "delay_minutes",
        "raw_delay_minutes",
        "prediction_clamped",
        "vehicle",
        "stop_role",
    )
    return {key: row.get(key) for key in keys if key in row}


def apply_catchable_guidance(
    snapshot: dict[str, Any],
    now: datetime,
    walking_minutes: int,
    margin_minutes: int = 0,
) -> dict[str, Any]:
    """Expose the first realistically catchable departure and the one after it.

    Catchability is intentionally simple and observable:

    departure_time >= now + effective walking time + configured margin.

    The function never changes the ETA engine, selected Next bus, or departure
    ordering. It only adds derived state for automations.
    """
    walking_minutes = max(0, int(walking_minutes))
    margin_minutes = max(0, int(margin_minutes))

    result: dict[str, Any] = {
        "status": "walking_disabled",
        "walking_minutes": walking_minutes,
        "margin_minutes": margin_minutes,
        "required_lead_minutes": walking_minutes + margin_minutes,
        "departure": None,
        "following_departure": None,
    }

    if walking_minutes <= 0:
        snapshot["catchable"] = result
        return snapshot

    departures = snapshot.get("departures")
    if not isinstance(departures, list) or not departures:
        result["status"] = "no_departures"
        snapshot["catchable"] = result
        return snapshot

    threshold = now + timedelta(minutes=walking_minutes + margin_minutes)

    catchable_index: int | None = None
    for index, raw_row in enumerate(departures):
        if not isinstance(raw_row, dict):
            continue
        departure_time = _parse_departure_time(raw_row)
        if departure_time is None:
            continue
        if departure_time.tzinfo is None and now.tzinfo is not None:
            departure_time = departure_time.replace(tzinfo=now.tzinfo)
        if departure_time >= threshold:
            catchable_index = index
            break

    if catchable_index is None:
        result["status"] = "none_in_window"
        snapshot["catchable"] = result
        return snapshot

    result["status"] = "ok"
    result["departure"] = _summary(departures[catchable_index])

    for raw_row in departures[catchable_index + 1 :]:
        if isinstance(raw_row, dict):
            result["following_departure"] = _summary(raw_row)
            break

    snapshot["catchable"] = result
    return snapshot
