"""Tests for the pure boarding-inference state machine."""

from __future__ import annotations

from custom_components.bods_bus_tracker.journey_inference import (
    BoardingEvidence,
    JourneyConfidence,
    JourneyInference,
    JourneyState,
    advance_journey,
)


def test_initial_and_public_state_are_privacy_safe() -> None:
    state = JourneyInference.initial()
    assert state.state is JourneyState.APPROACHING_STOP
    assert state.confidence is JourneyConfidence.LOW
    public = state.public_state()
    assert set(public) == {
        "state",
        "confidence",
        "reasons",
        "rejections",
        "confirmation_count",
    }
    flattened = repr(public).lower()
    for forbidden in ("latitude", "longitude", "person.", "device_tracker", "api_key"):
        assert forbidden not in flattened


def test_walking_past_stop_never_becomes_waiting() -> None:
    state = advance_journey(
        JourneyInference.initial(),
        BoardingEvidence(near_boarding_stop=True),
    )
    assert state.state is JourneyState.APPROACHING_STOP
    assert state.rejections == ("dwell_not_confirmed",)


def test_not_near_stop_stays_approaching() -> None:
    state = advance_journey(JourneyInference.initial(), BoardingEvidence())
    assert state.rejections == ("not_near_boarding_stop",)


def test_dwell_moves_to_waiting_and_records_bus_evidence() -> None:
    waiting = advance_journey(
        JourneyInference.initial(),
        BoardingEvidence(near_boarding_stop=True, dwell_confirmed=True),
    )
    assert waiting.state is JourneyState.WAITING_AT_STOP

    waiting = advance_journey(
        waiting,
        BoardingEvidence(
            near_boarding_stop=True,
            dwell_confirmed=True,
            departure_plausible=True,
            matched_vehicle_at_stop=True,
        ),
    )
    assert waiting.reasons == (
        "near_boarding_stop",
        "dwell_confirmed",
        "departure_plausible",
        "matched_vehicle_at_stop",
    )


def test_waiting_but_not_boarding_resets() -> None:
    waiting = JourneyInference(
        JourneyState.WAITING_AT_STOP,
        JourneyConfidence.MEDIUM,
    )
    state = advance_journey(
        waiting,
        BoardingEvidence(departed_stop=True),
    )
    assert state.state is JourneyState.APPROACHING_STOP
    assert state.rejections == ("left_stop_without_plausible_departure",)


def test_plausible_departure_reaches_only_possible_boarding() -> None:
    waiting = JourneyInference(
        JourneyState.WAITING_AT_STOP,
        JourneyConfidence.MEDIUM,
    )
    state = advance_journey(
        waiting,
        BoardingEvidence(departed_stop=True, departure_plausible=True),
    )
    assert state.state is JourneyState.POSSIBLE_BOARDING


def test_walking_after_stop_rejects_boarding() -> None:
    possible = JourneyInference(
        JourneyState.POSSIBLE_BOARDING,
        JourneyConfidence.MEDIUM,
    )
    state = advance_journey(possible, BoardingEvidence(walking_like=True))
    assert state.state is JourneyState.APPROACHING_STOP
    assert state.rejections == ("walking_motion_after_stop",)


def test_car_like_departure_needs_matched_vehicle() -> None:
    possible = JourneyInference(
        JourneyState.POSSIBLE_BOARDING,
        JourneyConfidence.MEDIUM,
    )
    state = advance_journey(possible, BoardingEvidence(bus_like=True))
    assert state.state is JourneyState.POSSIBLE_BOARDING
    assert state.rejections == ("bus_like_without_matched_vehicle_departure",)


def test_weak_possible_boarding_stays_unconfirmed() -> None:
    possible = JourneyInference(
        JourneyState.POSSIBLE_BOARDING,
        JourneyConfidence.MEDIUM,
    )
    state = advance_journey(possible, BoardingEvidence())
    assert state.rejections == ("bus_like_motion_not_confirmed",)


def test_matched_vehicle_departure_creates_candidate() -> None:
    possible = JourneyInference(
        JourneyState.POSSIBLE_BOARDING,
        JourneyConfidence.MEDIUM,
    )
    candidate = advance_journey(
        possible,
        BoardingEvidence(
            bus_like=True,
            matched_vehicle_departed=True,
            route_progress_consistent=True,
        ),
    )
    assert candidate.state is JourneyState.ON_BUS_CANDIDATE
    assert candidate.confirmation_count == 1
    assert "route_progress_consistent" in candidate.reasons


def test_candidate_requires_repeated_strong_confirmation() -> None:
    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        confirmation_count=1,
    )
    confirmed = advance_journey(
        candidate,
        BoardingEvidence(
            bus_like=True,
            matched_vehicle_departed=True,
            route_progress_consistent=True,
        ),
    )
    assert confirmed.state is JourneyState.ON_BUS_CONFIRMED
    assert confirmed.confirmation_count == 2
    assert "repeated_strong_confirmation" in confirmed.reasons


def test_candidate_first_strong_confirmation_remains_candidate() -> None:
    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        confirmation_count=0,
    )
    state = advance_journey(
        candidate,
        BoardingEvidence(
            bus_like=True,
            matched_vehicle_departed=True,
            route_progress_consistent=True,
        ),
    )
    assert state.state is JourneyState.ON_BUS_CANDIDATE
    assert state.confirmation_count == 1


def test_candidate_without_repeat_stays_candidate() -> None:
    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        reasons=("bus_like_motion",),
        confirmation_count=1,
    )
    state = advance_journey(candidate, BoardingEvidence(bus_like=True))
    assert state.state is JourneyState.ON_BUS_CANDIDATE
    assert state.rejections == ("strong_confirmation_not_repeated",)


def test_walking_after_candidate_rejects_candidate() -> None:
    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        confirmation_count=1,
    )
    state = advance_journey(candidate, BoardingEvidence(walking_like=True))
    assert state.state is JourneyState.APPROACHING_STOP


def test_wrong_service_and_route_contradictions_reject() -> None:
    possible = JourneyInference(
        JourneyState.POSSIBLE_BOARDING,
        JourneyConfidence.MEDIUM,
    )
    wrong = advance_journey(
        possible,
        BoardingEvidence(wrong_service_evidence=True),
    )
    assert wrong.state is JourneyState.APPROACHING_STOP
    assert wrong.rejections == ("wrong_service_evidence",)

    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        confirmation_count=1,
    )
    contradicted = advance_journey(
        candidate,
        BoardingEvidence(contradictory_route=True),
    )
    assert contradicted.state is JourneyState.POSSIBLE_BOARDING
    assert contradicted.rejections == ("contradictory_route",)


def test_timetable_only_can_be_possible_not_confirmed() -> None:
    waiting = JourneyInference(
        JourneyState.WAITING_AT_STOP,
        JourneyConfidence.MEDIUM,
    )
    possible = advance_journey(
        waiting,
        BoardingEvidence(departed_stop=True, departure_plausible=True),
    )
    possible = advance_journey(possible, BoardingEvidence(bus_like=True))
    assert possible.state is JourneyState.POSSIBLE_BOARDING


def test_terminus_requires_independent_matched_departure() -> None:
    waiting = JourneyInference(
        JourneyState.WAITING_AT_STOP,
        JourneyConfidence.MEDIUM,
    )
    possible = advance_journey(
        waiting,
        BoardingEvidence(departed_stop=True, departure_plausible=True),
    )
    candidate = advance_journey(
        possible,
        BoardingEvidence(bus_like=True, matched_vehicle_departed=True),
    )
    assert candidate.state is JourneyState.ON_BUS_CANDIDATE


def test_stale_updates_freeze_state() -> None:
    candidate = JourneyInference(
        JourneyState.ON_BUS_CANDIDATE,
        JourneyConfidence.HIGH,
        reasons=("bus_like_motion",),
        confirmation_count=1,
    )
    state = advance_journey(
        candidate,
        BoardingEvidence(
            updates_fresh=False,
            bus_like=True,
            matched_vehicle_departed=True,
            route_progress_consistent=True,
        ),
    )
    assert state.state is JourneyState.ON_BUS_CANDIDATE
    assert state.confirmation_count == 1
    assert state.rejections == ("updates_stale",)


def test_confirmed_journey_requires_destination_and_alighting() -> None:
    confirmed = JourneyInference(
        JourneyState.ON_BUS_CONFIRMED,
        JourneyConfidence.CONFIRMED,
        reasons=("repeated_strong_confirmation",),
        confirmation_count=2,
    )
    still = advance_journey(
        confirmed,
        BoardingEvidence(near_destination=True),
    )
    assert still.state is JourneyState.ON_BUS_CONFIRMED

    arrived = advance_journey(
        confirmed,
        BoardingEvidence(near_destination=True, alighting_motion=True),
    )
    assert arrived.state is JourneyState.ARRIVED_ALIGHTED


def test_arrived_state_is_terminal() -> None:
    arrived = JourneyInference(
        JourneyState.ARRIVED_ALIGHTED,
        JourneyConfidence.CONFIRMED,
        confirmation_count=2,
    )
    assert advance_journey(arrived, BoardingEvidence()) is arrived


def test_unhandled_state_guard() -> None:
    class FakeState:
        pass

    invalid = JourneyInference.__new__(JourneyInference)
    object.__setattr__(invalid, "state", FakeState())
    object.__setattr__(invalid, "confidence", JourneyConfidence.LOW)
    object.__setattr__(invalid, "reasons", ())
    object.__setattr__(invalid, "rejections", ())
    object.__setattr__(invalid, "confirmation_count", 0)

    try:
        advance_journey(invalid, BoardingEvidence())
    except AssertionError as exc:
        assert "Unhandled journey state" in str(exc)
    else:
        raise AssertionError("Expected unhandled-state guard")
