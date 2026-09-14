"""Privacy-preserving evidence adapter for boarding inference.

This module converts transient location fixes plus already-trusted BODS journey signals
into the boolean evidence consumed by journey_inference. Raw coordinates are never
stored in the returned memory or public evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

from .journey_inference import BoardingEvidence


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    """Prototype thresholds used to derive conservative traveller evidence."""

    boarding_enter_radius_m: float = 75.0
    boarding_exit_radius_m: float = 120.0
    destination_radius_m: float = 100.0
    maximum_accuracy_m: float = 50.0
    dwell_seconds: float = 60.0
    fresh_seconds: float = 120.0
    motion_min_interval_seconds: float = 10.0
    motion_max_interval_seconds: float = 180.0
    walking_max_mps: float = 2.5
    vehicle_min_mps: float = 4.0
    departure_before_seconds: float = 180.0
    departure_after_seconds: float = 300.0


@dataclass(frozen=True, slots=True)
class LocationFix:
    """One transient traveller location fix."""

    latitude: float
    longitude: float
    observed_at: datetime
    accuracy_m: float | None = None


@dataclass(frozen=True, slots=True)
class TrustedBusEvidence:
    """Journey signals already derived by the trusted BODS matching/timing layer."""

    departure_expected: datetime | None = None
    matched_vehicle_at_stop: bool = False
    matched_vehicle_departed: bool = False
    route_progress_consistent: bool = False
    wrong_service_evidence: bool = False
    contradictory_route: bool = False
    alighting_motion: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceMemory:
    """Persisted derived memory with no raw location coordinates."""

    near_stop_since: datetime | None = None
    was_near_stop: bool = False
    was_bus_like: bool = False

    def private_debug_state(self) -> dict[str, object]:
        """Return a coordinate-free internal debug representation."""
        return {
            "near_stop_since": (
                self.near_stop_since.isoformat()
                if self.near_stop_since is not None
                else None
            ),
            "was_near_stop": self.was_near_stop,
            "was_bus_like": self.was_bus_like,
        }


@dataclass(frozen=True, slots=True)
class EvidenceResult:
    """Derived inference evidence and next coordinate-free memory."""

    evidence: BoardingEvidence
    memory: EvidenceMemory


def _distance_metres(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Return great-circle distance between two WGS84 points in metres."""
    earth_m = 6_371_000.0
    p1 = math.radians(latitude_a)
    p2 = math.radians(latitude_b)
    dlat = math.radians(latitude_b - latitude_a)
    dlon = math.radians(longitude_b - longitude_a)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * earth_m * math.asin(math.sqrt(a))


def _accurate_enough(fix: LocationFix, policy: EvidencePolicy) -> bool:
    """Return whether a fix is accurate enough for proximity claims."""
    return fix.accuracy_m is None or (
        math.isfinite(fix.accuracy_m)
        and 0 <= fix.accuracy_m <= policy.maximum_accuracy_m
    )


def _fresh_enough(
    fix: LocationFix,
    now: datetime,
    policy: EvidencePolicy,
) -> bool:
    """Return whether the traveller fix is recent enough to influence state."""
    age = (now - fix.observed_at).total_seconds()
    return 0 <= age <= policy.fresh_seconds


def _near_with_hysteresis(
    distance_m: float,
    was_near: bool,
    policy: EvidencePolicy,
) -> bool:
    """Apply an enter/exit radius pair to reduce GPS boundary chatter."""
    threshold = (
        policy.boarding_exit_radius_m
        if was_near
        else policy.boarding_enter_radius_m
    )
    return distance_m <= threshold


def _motion_speed_mps(
    previous_fix: LocationFix | None,
    current_fix: LocationFix,
    policy: EvidencePolicy,
) -> float | None:
    """Derive speed transiently without retaining either coordinate pair."""
    if previous_fix is None:
        return None
    if not _accurate_enough(previous_fix, policy):
        return None

    seconds = (current_fix.observed_at - previous_fix.observed_at).total_seconds()
    if not (
        policy.motion_min_interval_seconds
        <= seconds
        <= policy.motion_max_interval_seconds
    ):
        return None

    distance = _distance_metres(
        previous_fix.latitude,
        previous_fix.longitude,
        current_fix.latitude,
        current_fix.longitude,
    )
    return distance / seconds


def _departure_plausible(
    expected: datetime | None,
    now: datetime,
    policy: EvidencePolicy,
) -> bool:
    """Return whether the trusted departure time is close enough to boarding."""
    if expected is None:
        return False
    delta = (expected - now).total_seconds()
    return -policy.departure_after_seconds <= delta <= policy.departure_before_seconds


def derive_boarding_evidence(
    *,
    previous_fix: LocationFix | None,
    current_fix: LocationFix,
    boarding_stop: tuple[float, float],
    destination_stop: tuple[float, float] | None,
    trusted_bus: TrustedBusEvidence,
    memory: EvidenceMemory,
    now: datetime,
    policy: EvidencePolicy | None = None,
) -> EvidenceResult:
    """Derive privacy-safe boarding evidence from transient local observations."""
    effective_policy = policy or EvidencePolicy()

    if not _fresh_enough(current_fix, now, effective_policy) or not _accurate_enough(
        current_fix, effective_policy
    ):
        return EvidenceResult(
            evidence=BoardingEvidence(updates_fresh=False),
            memory=memory,
        )

    stop_distance = _distance_metres(
        current_fix.latitude,
        current_fix.longitude,
        boarding_stop[0],
        boarding_stop[1],
    )
    near_stop = _near_with_hysteresis(
        stop_distance,
        memory.was_near_stop,
        effective_policy,
    )

    near_stop_since = memory.near_stop_since
    if near_stop:
        if near_stop_since is None:
            near_stop_since = current_fix.observed_at
    else:
        near_stop_since = None

    dwell_confirmed = (
        near_stop
        and near_stop_since is not None
        and (current_fix.observed_at - near_stop_since).total_seconds()
        >= effective_policy.dwell_seconds
    )
    departed_stop = memory.was_near_stop and not near_stop

    speed_mps = _motion_speed_mps(previous_fix, current_fix, effective_policy)
    walking_like = (
        speed_mps is not None and speed_mps <= effective_policy.walking_max_mps
    )
    bus_like = (
        speed_mps is not None and speed_mps >= effective_policy.vehicle_min_mps
    )

    near_destination = False
    if destination_stop is not None:
        destination_distance = _distance_metres(
            current_fix.latitude,
            current_fix.longitude,
            destination_stop[0],
            destination_stop[1],
        )
        near_destination = destination_distance <= effective_policy.destination_radius_m

    evidence = BoardingEvidence(
        updates_fresh=True,
        near_boarding_stop=near_stop,
        dwell_confirmed=dwell_confirmed,
        departure_plausible=_departure_plausible(
            trusted_bus.departure_expected,
            now,
            effective_policy,
        ),
        departed_stop=departed_stop,
        walking_like=walking_like,
        bus_like=bus_like,
        matched_vehicle_at_stop=trusted_bus.matched_vehicle_at_stop,
        matched_vehicle_departed=trusted_bus.matched_vehicle_departed,
        route_progress_consistent=trusted_bus.route_progress_consistent,
        wrong_service_evidence=trusted_bus.wrong_service_evidence,
        contradictory_route=trusted_bus.contradictory_route,
        near_destination=near_destination,
        alighting_motion=trusted_bus.alighting_motion,
    )
    return EvidenceResult(
        evidence=evidence,
        memory=EvidenceMemory(
            near_stop_since=near_stop_since,
            was_near_stop=near_stop,
            was_bus_like=bus_like or memory.was_bus_like,
        ),
    )
