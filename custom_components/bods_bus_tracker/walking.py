"""Walking-time guidance for BODS Bus Tracker."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any


def normalise_dynamic_walking_minutes(
    value: object,
    unit: str | None,
    maximum_minutes: int,
) -> float | None:
    """Normalise a Home Assistant duration-like sensor state to minutes."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric) or numeric < 0:
        return None

    unit_key = (unit or "").strip().casefold()
    if unit_key in {"min", "minute", "minutes"}:
        minutes = numeric
    elif unit_key in {"s", "sec", "second", "seconds"}:
        minutes = numeric / 60
    elif unit_key in {"h", "hr", "hour", "hours"}:
        minutes = numeric * 60
    else:
        return None

    if minutes > maximum_minutes:
        return None
    return minutes


def apply_walking_guidance(
    snapshot: dict[str, Any],
    now: datetime,
    walking_minutes: int,
    *,
    walking_mode: str = "static",
    walking_time_entity: str | None = None,
    walking_dynamic_minutes: float | None = None,
    walking_fallback: bool = False,
    walking_source_status: str = "ok",
) -> dict[str, Any]:
    """Add leave-by guidance without changing the underlying ETA."""
    next_bus = snapshot.get("next_bus")
    if not isinstance(next_bus, dict):
        return snapshot

    walking_minutes = max(0, int(walking_minutes))
    next_bus["walking_minutes"] = walking_minutes
    next_bus["walking_mode"] = walking_mode
    next_bus["walking_time_entity"] = walking_time_entity
    next_bus["walking_dynamic_minutes"] = walking_dynamic_minutes
    next_bus["walking_fallback"] = walking_fallback
    next_bus["walking_source_status"] = walking_source_status
    next_bus["leave_by"] = None
    next_bus["leave_in_minutes"] = None
    next_bus["leave_now"] = False

    if walking_minutes <= 0 or not next_bus.get("available"):
        return snapshot

    expected_value = next_bus.get("expected")
    if not expected_value:
        return snapshot

    try:
        expected = datetime.fromisoformat(str(expected_value))
    except (TypeError, ValueError):
        return snapshot

    if expected.tzinfo is None and now.tzinfo is not None:
        expected = expected.replace(tzinfo=now.tzinfo)

    leave_by = expected - timedelta(minutes=walking_minutes)
    next_bus["leave_by"] = leave_by.isoformat()

    # Once the expected bus time has passed, guidance for that departure is
    # no longer actionable. The next coordinator refresh will naturally move
    # on to the next departure when the ETA engine does.
    if now >= expected:
        return snapshot

    seconds_until_leave = (leave_by - now).total_seconds()
    if seconds_until_leave <= 0:
        next_bus["leave_in_minutes"] = 0
        next_bus["leave_now"] = True
    else:
        next_bus["leave_in_minutes"] = max(1, math.ceil(seconds_until_leave / 60))

    return snapshot
