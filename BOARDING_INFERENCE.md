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

The read-only evidence adapter now calculates the traveller-side booleans from transient Home Assistant location fixes while keeping the inference result and retained memory coordinate-free. Trusted bus/route signals remain inputs from the existing BODS matching/timing layer rather than being recalculated.

## Read-only evidence adapter

Two new modules keep location handling separate from inference policy:

- `journey_evidence_ha.py` reads a Home Assistant `State` and creates one transient `LocationFix`;
- `journey_evidence.py` converts the current/previous transient fixes plus trusted BODS journey signals into `BoardingEvidence`.

The adapter does not subscribe to entities yet, write entities, notify users, call the network or add raw coordinates to diagnostics.

### Coordinate-retention rule

Raw latitude/longitude may exist only inside the current adapter call and the transient old/new Home Assistant states already supplied by Home Assistant.

Persisted adapter memory contains only:

- the time continuous stop proximity began;
- whether the previous derived state was near the boarding stop;
- whether vehicle-like motion has been observed.

No coordinate pair, person entity ID or device-tracker entity ID is retained.

### Motion without stored coordinates

Motion is calculated from the transient previous/current fixes supplied for one update. The coordinates are discarded after the evidence calculation.

The initial prototype deliberately has three motion bands:

- walking-like: at or below **2.5 m/s**;
- unknown/ambiguous: between **2.5 and 4.0 m/s**;
- vehicle-like (`bus_like` evidence): at or above **4.0 m/s**.

The name `bus_like` does **not** mean the motion itself proves a bus. Vehicle-like speed can also be a car, taxi or bicycle. The state model therefore still requires independently matched bus evidence before it can progress to `on_bus_candidate`.

### Stop proximity and dwell

Initial validation thresholds are deliberately internal prototype policy, not user configuration:

- enter boarding-stop radius: **75 m**;
- exit boarding-stop radius: **120 m**;
- maximum accepted GPS accuracy: **50 m**;
- continuous dwell required: **60 s**;
- location freshness: **120 s**.

The different enter/exit radii provide hysteresis so GPS jitter at the boundary does not repeatedly enter/leave the stop.

Poor or stale fixes freeze inference rather than creating positive evidence.

### Departure timing

`departure_plausible` uses the trusted passenger-facing expected departure time already derived by BODS.

The initial prototype window is:

- up to **3 minutes before** expected departure;
- up to **5 minutes after** expected departure.

This only permits progression to `possible_boarding`. Timing alone still cannot confirm boarding.

### Trusted bus evidence boundary

The evidence adapter deliberately does **not** repeat live-to-GTFS matching.

These inputs must come from the existing trusted BODS timing/matching layer or a future private coordinator observation derived from it:

- `matched_vehicle_at_stop`;
- `matched_vehicle_departed`;
- `route_progress_consistent`;
- `wrong_service_evidence`;
- `contradictory_route`.

This is especially important at termini: the evidence must represent an independently matched **outbound** journey. An inbound vehicle is never treated as proof of the outbound service.

`alighting_motion` is also intentionally not inferred from low speed alone. A bus stopped at the destination could otherwise look like a traveller who has alighted. It remains a future stronger derived signal.

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

## Current validation state

The pure state model and read-only evidence adapter are implemented and remain isolated from Home Assistant behaviour.

Current branch CI after the evidence-adapter milestone:

- **226 tests passed**;
- **100.00% integration line coverage**;
- `journey_inference.py`: 100%;
- `journey_evidence.py`: 100%;
- `journey_evidence_ha.py`: 100%;
- hassfest, HACS validation, strict mypy, version and cache-policy checks: green.

## Next validation stages

1. Define the private coordinator observation needed to supply trusted matched-vehicle departure and route-progress signals **without re-running matching**.
2. Add a read-only Home Assistant wiring layer that listens to the configured traveller and updates inference state without notifications.
3. Expose diagnostic/observable state only.
4. Gather real journey traces.
5. Review false positives and false negatives.
6. Only then decide whether `on_bus_confirmed` is reliable enough to drive ETA/notification behaviour.
