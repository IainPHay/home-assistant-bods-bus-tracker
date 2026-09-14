"""Read-only Home Assistant location-state adapter for journey inference.

The functions in this module only read State attributes and return a transient
LocationFix. They do not subscribe to state changes, store coordinates, write entities
or emit diagnostics.
"""

from __future__ import annotations

import math

from homeassistant.core import State

from .journey_evidence import LocationFix


def location_fix_from_state(state: State | None) -> LocationFix | None:
    """Extract one transient location fix from a Home Assistant state."""
    if state is None:
        return None

    latitude = state.attributes.get("latitude")
    longitude = state.attributes.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(
        longitude, (int, float)
    ):
        return None

    lat = float(latitude)
    lon = float(longitude)
    if (
        not math.isfinite(lat)
        or not math.isfinite(lon)
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
    ):
        return None

    accuracy_value = state.attributes.get("gps_accuracy")
    accuracy: float | None = None
    if isinstance(accuracy_value, (int, float)):
        candidate = float(accuracy_value)
        if math.isfinite(candidate) and candidate >= 0:
            accuracy = candidate

    return LocationFix(
        latitude=lat,
        longitude=lon,
        observed_at=state.last_updated,
        accuracy_m=accuracy,
    )
