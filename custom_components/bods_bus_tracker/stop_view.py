"""Passenger-facing stop views built on top of the existing ETA engine.

This module deliberately does not alter live-to-GTFS matching or ETA estimation.
It partitions the already-calculated candidate journeys into arrivals and departures,
and adds conservative terminus state derived only from the selected GTFS trip and the
live vehicle position.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .api import ServiceSpec, Trip, calculate_candidates, candidate_dict
from .const import (
    AT_STOP_DISTANCE_METRES,
    STOP_VIEW_ARRIVALS,
    STOP_VIEW_BOTH,
    STOP_VIEW_DEPARTURES,
)


def _distance_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 points in metres."""
    earth_m = 6_371_000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * earth_m * math.asin(math.sqrt(a))


def _trip_role(trip: Trip, target_stop: str) -> str | None:
    target = trip.target(target_stop)
    if target is None:
        return None
    target_index = trip.stops.index(target)
    if target_index == 0:
        return "origin"
    if target_index == len(trip.stops) - 1:
        return "destination"
    return "intermediate"


def _stop_profile(trips: list[Trip], target_stop: str) -> dict[str, object]:
    roles = {
        role
        for trip in trips
        if (role := _trip_role(trip, target_stop)) is not None
    }
    has_origins = "origin" in roles
    has_destinations = "destination" in roles
    has_intermediate = "intermediate" in roles
    if has_origins and has_destinations:
        profile = "terminus"
    elif has_origins:
        profile = "origin"
    elif has_destinations:
        profile = "destination"
    else:
        profile = "intermediate"
    return {
        "profile": profile,
        "has_origins": has_origins,
        "has_destinations": has_destinations,
        "has_intermediate": has_intermediate,
        "combined_supported": has_origins and has_destinations,
    }


def _enrich_row(
    row: dict[str, object],
    trip: Trip | None,
    target_stop: str,
) -> dict[str, object]:
    enriched = dict(row)
    role = enriched.get("stop_role")
    enriched["event_type"] = (
        "departure"
        if role == "origin"
        else "arrival"
        if role == "destination"
        else "call"
    )

    if trip is None:
        enriched["origin"] = None
        enriched["distance_to_stop_m"] = None
        enriched["at_stop"] = False
        return enriched

    enriched["origin"] = trip.origin.name
    target = trip.target(target_stop)
    latitude = enriched.get("latitude")
    longitude = enriched.get("longitude")
    if (
        target is None
        or latitude is None
        or longitude is None
        or not enriched.get("realtime")
    ):
        enriched["distance_to_stop_m"] = None
        enriched["at_stop"] = False
        return enriched

    distance = _distance_metres(
        float(latitude),
        float(longitude),
        target.lat,
        target.lon,
    )
    enriched["distance_to_stop_m"] = round(distance)
    enriched["at_stop"] = distance <= AT_STOP_DISTANCE_METRES
    return enriched


def _first_for_service(
    rows: list[dict[str, object]], service: ServiceSpec
) -> dict[str, object] | None:
    return next((row for row in rows if row.get("service_key") == service.key), None)


def apply_stop_view(
    snapshot: dict[str, Any],
    trips: list[Trip],
    vehicles,
    now: datetime,
    target_stop: str,
    services: list[ServiceSpec],
    stop_view: str,
    max_live_age_seconds: int,
) -> dict[str, Any]:
    """Partition ETA candidates into departures/arrivals and add terminus state.

    `departures` retains intermediate-stop calls so the established passenger-facing
    behaviour at ordinary boarding stops remains unchanged. Destination-only journeys
    are excluded from departures because they terminate at the monitored stop.

    In `both` mode, `next_bus` deliberately remains the next departure. This keeps the
    walking-time feature and existing boarding automations tied to a boardable journey.
    """
    candidates, _ = calculate_candidates(
        trips,
        list(vehicles),
        now,
        target_stop=target_stop,
        max_live_age_seconds=max_live_age_seconds,
    )
    trip_by_id = {trip.trip_id: trip for trip in trips}
    rows = [
        _enrich_row(
            candidate_dict(candidate, now),
            trip_by_id.get(candidate.trip_id),
            target_stop,
        )
        for candidate in candidates
    ]

    departures = [
        row for row in rows if row.get("stop_role") in {"origin", "intermediate"}
    ]
    arrivals = [
        row for row in rows if row.get("stop_role") in {"destination", "intermediate"}
    ]

    next_departure = departures[0] if departures else candidate_dict(None, now)
    next_arrival = arrivals[0] if arrivals else candidate_dict(None, now)
    selected_rows = arrivals if stop_view == STOP_VIEW_ARRIVALS else departures
    selected_next = selected_rows[0] if selected_rows else candidate_dict(None, now)

    per_service: dict[str, dict[str, object]] = {}
    for service in services:
        first = _first_for_service(selected_rows, service)
        per_service[service.key] = (
            dict(first) if first is not None else candidate_dict(None, now, service)
        )

    at_stand_departures = [
        row
        for row in departures
        if row.get("stop_role") == "origin"
        and row.get("realtime")
        and row.get("at_stop")
    ]
    arrived_vehicles = [
        row
        for row in arrivals
        if row.get("stop_role") == "destination"
        and row.get("realtime")
        and row.get("at_stop")
    ]
    approaching_arrivals = [
        row
        for row in arrivals
        if row.get("stop_role") == "destination"
        and row.get("realtime")
        and not row.get("at_stop")
        and row.get("minutes") is not None
        and int(row["minutes"]) <= 5
    ]

    profile = _stop_profile(trips, target_stop)
    stop = dict(snapshot.get("stop", {}))
    stop["view_mode"] = stop_view
    stop.update(profile)

    snapshot["stop"] = stop
    snapshot["stop_view"] = stop_view
    snapshot["next_bus"] = dict(selected_next)
    snapshot["next_departure"] = dict(next_departure)
    snapshot["next_arrival"] = dict(next_arrival)
    snapshot["departures"] = [dict(row) for row in departures[:12]]
    snapshot["arrivals"] = [dict(row) for row in arrivals[:12]]
    snapshot["services"] = per_service
    snapshot["terminus"] = {
        **profile,
        "at_stand_departures": [dict(row) for row in at_stand_departures[:4]],
        "arrived_vehicles": [dict(row) for row in arrived_vehicles[:4]],
        "approaching_arrivals": [dict(row) for row in approaching_arrivals[:4]],
        "linking_policy": "Only an outbound live journey at the stop is labelled at stand; incoming journeys are never assumed to form the next departure.",
    }
    return snapshot
