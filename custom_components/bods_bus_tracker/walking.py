"""Walking-time guidance for BODS Bus Tracker."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any


def apply_walking_guidance(
    snapshot: dict[str, Any], now: datetime, walking_minutes: int
) -> dict[str, Any]:
    """Add leave-by guidance without changing the underlying ETA."""
    next_bus = snapshot.get("next_bus")
    if not isinstance(next_bus, dict):
        return snapshot

    walking_minutes = max(0, int(walking_minutes))
    next_bus["walking_minutes"] = walking_minutes
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
