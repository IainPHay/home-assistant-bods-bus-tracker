# Boarding inference prototype

**Status:** design/prototype only  
**Branch:** feature/v0.7-boarding-inference  
**Tracking:** issue #11

This work is intentionally isolated from the beta.4 zone-exit release candidate.

The first milestone is **observable state only**. It must not send boarding, ETA, approaching-destination or arrival notifications.

## Design objective

Infer a likely journey state conservatively from already-derived Home Assistant/BODS evidence while preferring false negatives over false positives.

The prototype must answer:

> What can we say about boarding from the evidence we actually have?

It must not answer:

> What probably happened if we fill in missing evidence?

## State model

~~~text
approaching_stop
  → waiting_at_stop
  → possible_boarding
  → on_bus_candidate
  → on_bus_confirmed
  → arrived_alighted
~~~

Transitions can be rejected or downgraded when later evidence contradicts boarding.

## Evidence boundary

The pure inference engine accepts derived booleans only.

Current evidence contract:

- updates_fresh
- near_boarding_stop
- dwell_confirmed
- departure_plausible
- departed_stop
- walking_like
- bus_like
- matched_vehicle_at_stop
- matched_vehicle_departed
- route_progress_consistent
- wrong_service_evidence
- contradictory_route
- near_destination
- alighting_motion

No raw latitude/longitude, person entity ID, device-tracker entity ID or routing-provider credential is accepted or emitted by the model.

A future Home Assistant adapter may calculate these booleans from private local state, but the inference result and diagnostics remain derived.

## Confidence model

Confidence is deliberately coarse and explainable:

- low
- medium
- high
- confirmed

The model also emits positive reasons, rejection/contradiction reason codes and a small confirmation counter.

There is no opaque weighted score.

## Conservative transition policy

### approaching_stop → waiting_at_stop

Requires both:

- traveller near the boarding stop;
- dwell confirmed.

Walking past the stop does not advance.

### waiting_at_stop → possible_boarding

Requires both:

- traveller left the stop;
- departure was independently plausible at that time.

Merely leaving the stop is rejected.

### possible_boarding → on_bus_candidate

Requires both:

- bus-like movement;
- the **independently matched intended vehicle** has departed.

Bus-like movement alone is insufficient because a car or taxi can produce similar motion.

### on_bus_candidate → on_bus_confirmed

Requires repeated strong evidence:

- bus-like movement;
- independently matched vehicle departed;
- movement/vehicle progress is consistent with the expected route;
- the strong evidence is observed again on a subsequent update.

One strong observation remains only a candidate.

### on_bus_confirmed → arrived_alighted

Requires both:

- near the configured destination;
- alighting-compatible movement/state.

## Terminus rule

At a terminus, matched_vehicle_at_stop and matched_vehicle_departed must refer to an **independently matched outbound journey**.

An inbound vehicle identity must never be treated as proof that it forms the outbound service.

This preserves the existing BODS terminus safety rule.

## Timetable-only behaviour

Timetable/expected-time evidence may make boarding **possible**, but the first prototype does not allow timetable-only evidence to reach on_bus_confirmed.

This is deliberately conservative.

If real-world testing later demonstrates a safe timetable-only confirmation path, it must be designed and tested explicitly rather than inferred by absence of live data.

## False-positive tests

The initial suite explicitly covers:

- walking past the stop;
- waiting but not boarding;
- leaving by car / bus-like speed without matched vehicle evidence;
- wrong-service evidence;
- contradictory route evidence;
- late/plausible timetable-only departure;
- terminus/origin boarding;
- stale traveller updates;
- loss of repeated strong evidence;
- arrival without alighting evidence.

Additional real-world traces should be added before any Home Assistant-facing automation is considered.

## Privacy-safe result

The pure result exposes only derived state, confidence, reasons, rejections and a confirmation counter. It contains no private coordinates or provider/account secrets.

## Implementation boundary

custom_components/bods_bus_tracker/journey_inference.py is intentionally pure:

- no Home Assistant imports;
- no network calls;
- no entity writes;
- no notifications;
- no timers;
- no raw position storage.

This keeps the state policy independently testable and lets us validate inference before deciding how, or whether, to expose it in Home Assistant.

## Next validation stages

1. Keep the pure model green under synthetic false-positive tests.
2. Design a read-only Home Assistant adapter that produces the derived evidence.
3. Expose diagnostic/observable state only.
4. Gather real journey traces.
5. Review false positives and false negatives.
6. Only then decide whether on_bus_confirmed is reliable enough to drive ETA/notification behaviour.
