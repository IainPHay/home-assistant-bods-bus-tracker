"""Tests for privacy-preserving boarding evidence derivation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.journey_evidence import (
    EvidenceMemory,
    EvidencePolicy,
    LocationFix,
    TrustedBusEvidence,
    _departure_plausible,
    _distance_metres,
    _motion_speed_mps,
    derive_boarding_evidence,
)

TZ = ZoneInfo("Europe/London")
NOW = datetime(2026, 9, 14, 15, 0, tzinfo=TZ)
STOP = (55.0000, -1.0000)


def _fix(
    latitude: float = 55.0,
    longitude: float = -1.0,
    *,
    seconds_ago: float = 0,
    accuracy: float | None = 10.0,
) -> LocationFix:
    return LocationFix(
        latitude=latitude,
        longitude=longitude,
        observed_at=NOW - timedelta(seconds=seconds_ago),
        accuracy_m=accuracy,
    )


def test_distance_and_motion_speed_are_transient() -> None:
    assert _distance_metres(55.0, -1.0, 55.0, -1.0) == 0
    previous = _fix(longitude=-1.001, seconds_ago=60)
    current = _fix()
    speed = _motion_speed_mps(previous, current, EvidencePolicy())
    assert speed is not None
    assert speed > 0


def test_motion_speed_rejects_missing_bad_accuracy_and_bad_interval() -> None:
    policy = EvidencePolicy()
    current = _fix()

    assert _motion_speed_mps(None, current, policy) is None
    assert (
        _motion_speed_mps(
            _fix(seconds_ago=60, accuracy=500),
            current,
            policy,
        )
        is None
    )
    assert _motion_speed_mps(_fix(seconds_ago=1), current, policy) is None


def test_departure_window_is_bounded() -> None:
    policy = EvidencePolicy()
    assert not _departure_plausible(None, NOW, policy)
    assert _departure_plausible(NOW + timedelta(seconds=120), NOW, policy)
    assert _departure_plausible(NOW - timedelta(seconds=240), NOW, policy)
    assert not _departure_plausible(NOW + timedelta(seconds=600), NOW, policy)
    assert not _departure_plausible(NOW - timedelta(seconds=600), NOW, policy)


def test_stale_or_inaccurate_fix_freezes_coordinate_free_memory() -> None:
    memory = EvidenceMemory(
        near_stop_since=NOW - timedelta(seconds=90),
        was_near_stop=True,
        was_bus_like=True,
    )

    stale = derive_boarding_evidence(
        previous_fix=None,
        current_fix=_fix(seconds_ago=300),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=memory,
        now=NOW,
    )
    assert stale.evidence.updates_fresh is False
    assert stale.memory is memory

    inaccurate = derive_boarding_evidence(
        previous_fix=None,
        current_fix=_fix(accuracy=100),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=memory,
        now=NOW,
    )
    assert inaccurate.evidence.updates_fresh is False
    assert inaccurate.memory is memory


def test_enter_radius_starts_dwell_without_immediate_confirmation() -> None:
    result = derive_boarding_evidence(
        previous_fix=None,
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=EvidenceMemory(),
        now=NOW,
    )

    assert result.evidence.near_boarding_stop is True
    assert result.evidence.dwell_confirmed is False
    assert result.memory.was_near_stop is True
    assert result.memory.near_stop_since == NOW


def test_continuous_near_stop_dwell_becomes_confirmed() -> None:
    memory = EvidenceMemory(
        near_stop_since=NOW - timedelta(seconds=90),
        was_near_stop=True,
    )

    result = derive_boarding_evidence(
        previous_fix=_fix(seconds_ago=60),
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=memory,
        now=NOW,
    )

    assert result.evidence.near_boarding_stop is True
    assert result.evidence.dwell_confirmed is True


def test_exit_hysteresis_and_departure_detection() -> None:
    memory = EvidenceMemory(
        near_stop_since=NOW - timedelta(seconds=90),
        was_near_stop=True,
    )
    current = _fix(latitude=55.0018)

    result = derive_boarding_evidence(
        previous_fix=_fix(latitude=55.0, seconds_ago=60),
        current_fix=current,
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(
            departure_expected=NOW + timedelta(seconds=60)
        ),
        memory=memory,
        now=NOW,
    )

    assert result.evidence.near_boarding_stop is False
    assert result.evidence.departed_stop is True
    assert result.evidence.departure_plausible is True
    assert result.memory.near_stop_since is None


def test_hysteresis_retains_near_state_between_enter_and_exit_radii() -> None:
    memory = EvidenceMemory(
        near_stop_since=NOW - timedelta(seconds=90),
        was_near_stop=True,
    )
    current = _fix(latitude=55.0008)

    result = derive_boarding_evidence(
        previous_fix=None,
        current_fix=current,
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=memory,
        now=NOW,
    )

    assert result.evidence.near_boarding_stop is True


def test_motion_classes_have_deliberate_unknown_gap() -> None:
    policy = EvidencePolicy(
        walking_max_mps=2.5,
        vehicle_min_mps=4.0,
    )

    walking = derive_boarding_evidence(
        previous_fix=LocationFix(55.0, -1.0001, NOW - timedelta(seconds=60), 10),
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=EvidenceMemory(),
        now=NOW,
        policy=policy,
    )
    assert walking.evidence.walking_like is True
    assert walking.evidence.bus_like is False

    ambiguous = derive_boarding_evidence(
        previous_fix=LocationFix(55.0, -1.0030, NOW - timedelta(seconds=60), 10),
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=EvidenceMemory(),
        now=NOW,
        policy=policy,
    )
    assert ambiguous.evidence.walking_like is False
    assert ambiguous.evidence.bus_like is False


def test_vehicle_like_motion_and_trusted_bus_signals_pass_through() -> None:
    result = derive_boarding_evidence(
        previous_fix=LocationFix(55.0, -1.0100, NOW - timedelta(seconds=60), 10),
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=STOP,
        trusted_bus=TrustedBusEvidence(
            departure_expected=NOW,
            matched_vehicle_at_stop=True,
            matched_vehicle_departed=True,
            route_progress_consistent=True,
            wrong_service_evidence=True,
            contradictory_route=True,
            alighting_motion=True,
        ),
        memory=EvidenceMemory(),
        now=NOW,
    )

    assert result.evidence.bus_like is True
    assert result.evidence.matched_vehicle_at_stop is True
    assert result.evidence.matched_vehicle_departed is True
    assert result.evidence.route_progress_consistent is True
    assert result.evidence.wrong_service_evidence is True
    assert result.evidence.contradictory_route is True
    assert result.evidence.near_destination is True
    assert result.evidence.alighting_motion is True
    assert result.memory.was_bus_like is True


def test_destination_absent_stays_false_and_debug_memory_has_no_coordinates() -> None:
    result = derive_boarding_evidence(
        previous_fix=None,
        current_fix=_fix(),
        boarding_stop=STOP,
        destination_stop=None,
        trusted_bus=TrustedBusEvidence(),
        memory=EvidenceMemory(),
        now=NOW,
    )

    assert result.evidence.near_destination is False
    debug = result.memory.private_debug_state()
    flattened = repr(debug).lower()
    assert "latitude" not in flattened
    assert "longitude" not in flattened
