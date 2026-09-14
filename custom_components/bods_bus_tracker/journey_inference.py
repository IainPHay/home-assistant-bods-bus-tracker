"""Pure conservative boarding-inference state machine.

This module deliberately has no Home Assistant side effects and accepts only derived
evidence. Raw person/device coordinates, entity IDs and routing-provider credentials do
not belong in this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JourneyState(StrEnum):
    """Observable journey-inference states."""

    APPROACHING_STOP = "approaching_stop"
    WAITING_AT_STOP = "waiting_at_stop"
    POSSIBLE_BOARDING = "possible_boarding"
    ON_BUS_CANDIDATE = "on_bus_candidate"
    ON_BUS_CONFIRMED = "on_bus_confirmed"
    ARRIVED_ALIGHTED = "arrived_alighted"


class JourneyConfidence(StrEnum):
    """Coarse confidence labels for the current inferred state."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONFIRMED = "confirmed"


@dataclass(frozen=True, slots=True)
class BoardingEvidence:
    """Derived evidence for one inference update."""

    updates_fresh: bool = True
    near_boarding_stop: bool = False
    dwell_confirmed: bool = False
    departure_plausible: bool = False
    departed_stop: bool = False
    walking_like: bool = False
    bus_like: bool = False
    matched_vehicle_at_stop: bool = False
    matched_vehicle_departed: bool = False
    route_progress_consistent: bool = False
    wrong_service_evidence: bool = False
    contradictory_route: bool = False
    near_destination: bool = False
    alighting_motion: bool = False


@dataclass(frozen=True, slots=True)
class JourneyInference:
    """Current journey-inference result and explainable evidence."""

    state: JourneyState
    confidence: JourneyConfidence
    reasons: tuple[str, ...] = ()
    rejections: tuple[str, ...] = ()
    confirmation_count: int = 0

    @classmethod
    def initial(cls) -> "JourneyInference":
        """Return the initial observable state."""
        return cls(
            state=JourneyState.APPROACHING_STOP,
            confidence=JourneyConfidence.LOW,
        )

    def public_state(self) -> dict[str, object]:
        """Return a diagnostics-safe representation of the inference result."""
        return {
            "state": self.state,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "rejections": list(self.rejections),
            "confirmation_count": self.confirmation_count,
        }


def _result(
    state: JourneyState,
    confidence: JourneyConfidence,
    *,
    reasons: tuple[str, ...] = (),
    rejections: tuple[str, ...] = (),
    confirmation_count: int = 0,
) -> JourneyInference:
    """Build one immutable result."""
    return JourneyInference(
        state=state,
        confidence=confidence,
        reasons=reasons,
        rejections=rejections,
        confirmation_count=confirmation_count,
    )


def advance_journey(
    previous: JourneyInference,
    evidence: BoardingEvidence,
) -> JourneyInference:
    """Advance journey inference conservatively from derived evidence."""
    if not evidence.updates_fresh:
        return _result(
            previous.state,
            previous.confidence,
            reasons=previous.reasons,
            rejections=("updates_stale",),
            confirmation_count=previous.confirmation_count,
        )

    contradiction = evidence.wrong_service_evidence or evidence.contradictory_route
    if contradiction:
        rejection = (
            "wrong_service_evidence"
            if evidence.wrong_service_evidence
            else "contradictory_route"
        )
        if previous.state in {
            JourneyState.ON_BUS_CONFIRMED,
            JourneyState.ON_BUS_CANDIDATE,
        }:
            return _result(
                JourneyState.POSSIBLE_BOARDING,
                JourneyConfidence.MEDIUM,
                rejections=(rejection,),
            )
        return _result(
            JourneyState.APPROACHING_STOP,
            JourneyConfidence.LOW,
            rejections=(rejection,),
        )

    if previous.state is JourneyState.ARRIVED_ALIGHTED:
        return previous

    if previous.state is JourneyState.APPROACHING_STOP:
        if evidence.near_boarding_stop and evidence.dwell_confirmed:
            return _result(
                JourneyState.WAITING_AT_STOP,
                JourneyConfidence.MEDIUM,
                reasons=("near_boarding_stop", "dwell_confirmed"),
            )
        if evidence.near_boarding_stop:
            return _result(
                JourneyState.APPROACHING_STOP,
                JourneyConfidence.LOW,
                reasons=("near_boarding_stop",),
                rejections=("dwell_not_confirmed",),
            )
        return _result(
            JourneyState.APPROACHING_STOP,
            JourneyConfidence.LOW,
            rejections=("not_near_boarding_stop",),
        )

    if previous.state is JourneyState.WAITING_AT_STOP:
        if evidence.near_boarding_stop:
            reasons = ["near_boarding_stop", "dwell_confirmed"]
            if evidence.departure_plausible:
                reasons.append("departure_plausible")
            if evidence.matched_vehicle_at_stop:
                reasons.append("matched_vehicle_at_stop")
            return _result(
                JourneyState.WAITING_AT_STOP,
                JourneyConfidence.MEDIUM,
                reasons=tuple(reasons),
            )
        if evidence.departed_stop and evidence.departure_plausible:
            return _result(
                JourneyState.POSSIBLE_BOARDING,
                JourneyConfidence.MEDIUM,
                reasons=("departed_stop", "departure_plausible"),
            )
        return _result(
            JourneyState.APPROACHING_STOP,
            JourneyConfidence.LOW,
            rejections=("left_stop_without_plausible_departure",),
        )

    if previous.state is JourneyState.POSSIBLE_BOARDING:
        if evidence.walking_like:
            return _result(
                JourneyState.APPROACHING_STOP,
                JourneyConfidence.LOW,
                rejections=("walking_motion_after_stop",),
            )
        if evidence.bus_like and evidence.matched_vehicle_departed:
            reasons = ["bus_like_motion", "matched_vehicle_departed"]
            if evidence.route_progress_consistent:
                reasons.append("route_progress_consistent")
            return _result(
                JourneyState.ON_BUS_CANDIDATE,
                JourneyConfidence.HIGH,
                reasons=tuple(reasons),
                confirmation_count=1,
            )
        rejections = []
        if evidence.bus_like and not evidence.matched_vehicle_departed:
            rejections.append("bus_like_without_matched_vehicle_departure")
        if not evidence.bus_like:
            rejections.append("bus_like_motion_not_confirmed")
        return _result(
            JourneyState.POSSIBLE_BOARDING,
            JourneyConfidence.MEDIUM,
            reasons=("departure_plausible",),
            rejections=tuple(rejections),
        )

    if previous.state is JourneyState.ON_BUS_CANDIDATE:
        if evidence.walking_like:
            return _result(
                JourneyState.APPROACHING_STOP,
                JourneyConfidence.LOW,
                rejections=("walking_motion_after_candidate",),
            )
        strong_confirmation = (
            evidence.bus_like
            and evidence.matched_vehicle_departed
            and evidence.route_progress_consistent
        )
        if strong_confirmation:
            confirmation_count = previous.confirmation_count + 1
            if confirmation_count >= 2:
                return _result(
                    JourneyState.ON_BUS_CONFIRMED,
                    JourneyConfidence.CONFIRMED,
                    reasons=(
                        "bus_like_motion",
                        "matched_vehicle_departed",
                        "route_progress_consistent",
                        "repeated_strong_confirmation",
                    ),
                    confirmation_count=confirmation_count,
                )
            return _result(
                JourneyState.ON_BUS_CANDIDATE,
                JourneyConfidence.HIGH,
                reasons=(
                    "bus_like_motion",
                    "matched_vehicle_departed",
                    "route_progress_consistent",
                ),
                confirmation_count=confirmation_count,
            )
        return _result(
            JourneyState.ON_BUS_CANDIDATE,
            JourneyConfidence.HIGH,
            reasons=previous.reasons,
            rejections=("strong_confirmation_not_repeated",),
            confirmation_count=previous.confirmation_count,
        )

    if previous.state is JourneyState.ON_BUS_CONFIRMED:
        if evidence.near_destination and evidence.alighting_motion:
            return _result(
                JourneyState.ARRIVED_ALIGHTED,
                JourneyConfidence.CONFIRMED,
                reasons=("near_destination", "alighting_motion"),
                confirmation_count=previous.confirmation_count,
            )
        return _result(
            JourneyState.ON_BUS_CONFIRMED,
            JourneyConfidence.CONFIRMED,
            reasons=previous.reasons,
            confirmation_count=previous.confirmation_count,
        )

    raise AssertionError(f"Unhandled journey state: {previous.state}")
