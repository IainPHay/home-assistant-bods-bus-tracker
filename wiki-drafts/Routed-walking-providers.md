# Routed walking providers

BODS Bus Tracker v0.6 is deliberately **provider-neutral**.

It does not call HERE, Google or another routing API itself. It consumes a Home Assistant entity representing a routed duration.

## Required sensor contract

A compatible source must provide a Home Assistant entity whose state is:

- numeric;
- finite;
- non-negative;
- a duration rather than distance or an arrival timestamp;
- measured in `s`, `min` or `h`.

BODS normalises that value to minutes and rounds up to a whole minute for leave guidance.

## Provider status

| Provider/source | v0.6 status | Dynamic origin | Walking mode | Notes |
| --- | --- | --- | --- | --- |
| HERE Travel Time | **Live-validated** | Yes, using a Home Assistant `person` in project testing | Pedestrian | Recommended reference setup for v0.6 |
| Google Maps Travel Time | Compatible in principle, not live-validated by this project for v0.6 | Supported by Home Assistant | Provider integration dependent | Requires Google billing/API setup |
| Other HA duration sensor | Provider-neutral compatibility | Depends on source | Depends on source | Works if it obeys the BODS duration contract |

## Why provider-neutral matters

This design means:

- routing credentials remain in the routing integration;
- BODS diagnostics do not need provider secrets;
- a different routing provider should not require changes to the BODS ETA engine;
- static walking remains a reliable fallback.

## Current recommendation

For v0.6 testers who want routed walking, use **HERE Travel Time** first because it has been exercised end-to-end with BODS Bus Tracker.

See [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time).

## v0.7 work

The next development cycle will investigate alternative providers, especially options with a useful free tier or no-cost/self-hosted routing.

The goal is to broaden the validated provider matrix without weakening the provider-neutral interface.
