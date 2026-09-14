# Routed walking providers

BODS Bus Tracker is deliberately **provider-neutral**.

It does not call HERE, Google or another routing API itself. It consumes a Home Assistant entity representing a routed duration.

This boundary remains unchanged in v0.7: routing providers stay outside the BODS ETA/matching engine.

## Required sensor contract

A compatible source must provide a Home Assistant entity whose state is:

- numeric;
- finite;
- non-negative;
- a duration rather than distance or an arrival timestamp;
- measured in `s`, `min` or `h`.

BODS normalises that value to minutes and rounds up to a whole minute for walking/catchability guidance.

## Provider status

| Provider/source | Project status | Dynamic origin | Walking mode | Notes |
| --- | --- | --- | --- | --- |
| HERE Travel Time | **Live-validated** | Yes, using a Home Assistant `person` | Pedestrian | Reference setup |
| Google Maps Travel Time | Compatible in principle; not the primary project validation path | Supported by Home Assistant | Walking support depends on provider configuration | Requires Google API/billing setup |
| Other HA duration sensor | Provider-neutral compatibility | Depends on source | Depends on source | Suitable if it obeys the BODS duration contract |

Waze remains inappropriate for pedestrian catchability because it is road/vehicle oriented rather than a walking router.

Alternative/self-hosted routing work should remain a separate Home Assistant provider layer rather than adding provider credentials or routing calls to BODS Bus Tracker.

## One routing sensor per boarding stop

This becomes particularly important once Catchable bus is used.

For a moving traveller, the routed duration should describe:

```text
current traveller location → this exact BODS boarding stop
```

If you monitor multiple stops, the safest architecture is normally **one duration sensor per stop**, each with:

- the same dynamic `person` / `device_tracker` origin if appropriate;
- a fixed destination matching that stop.

### Why this matters

A shared duration sensor can return a completely valid number while pointing to the wrong destination.

For example, a walking sensor configured for Haymarket can legitimately report a long route while a different BODS stop is being evaluated. BODS has no way to know that the duration belongs to another destination: it only sees a duration entity.

The configured **Maximum routed walking time** may reject an extreme value and use static fallback, but that safety net should not be treated as destination validation.

## Static fallback

Always configure a sensible static walking time where practical.

BODS can fall back to it when the routed duration is:

- unavailable;
- unknown;
- stale;
- invalid;
- above the configured maximum.

The default maximum routed walking time is **120 minutes** and can be changed per stop.

## Catchability in v0.7

Catchable bus uses the already-resolved **effective walking minutes**.

The routing provider itself does not need to know anything about buses.

BODS then adds the explicit per-stop safety margin:

```text
required lead = effective walking time + catchable margin
```

See [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications).

## Why provider-neutral matters

This design means:

- routing credentials remain in the routing integration;
- person/device coordinates do not need to enter BODS;
- BODS diagnostics do not need provider secrets;
- changing routing provider does not require an ETA-engine rewrite;
- static walking remains a reliable fallback.

## Current recommendation

HERE Travel Time remains the reference provider because it has been exercised end-to-end with BODS Bus Tracker, including a moving Home Assistant `person` origin.

See [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time).

---