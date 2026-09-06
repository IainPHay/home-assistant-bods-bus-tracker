# Changelog

## 0.6.0-beta.2 — in development

- Added optional per-stop **routed dynamic walking time** using a Home Assistant travel-time sensor while retaining the configured static walking time as a safe fallback.
- Kept routing provider-neutral: BODS Bus Tracker consumes an existing Home Assistant duration sensor rather than storing HERE/Google credentials or calling routing providers directly.
- Added support for duration sensors reporting seconds, minutes or hours, with valid routed times rounded up to the next whole minute for passenger leave guidance.
- Added safe fallback for missing, unavailable, stale, invalid or excessive routed travel-time values; existing static-only stops remain unchanged unless dynamic walking is explicitly enabled.
- Kept `Leave by`, `Leave in` and `Leave now` tied to the next boardable departure and kept all dynamic-walking processing downstream of the BODS/GTFS ETA-matching engine.
- Added dynamic-walking runtime attributes and diagnostics without copying person/device coordinates into BODS Bus Tracker state.
- Added `DYNAMIC_WALKING.md` with provider-neutral setup guidance and HERE Travel Time / Google Maps Travel Time examples.
- Declared the integration as `single_config_entry` so Home Assistant no longer offers a redundant second BODS account/hub while retaining the native **Add bus stop** subentry action.
- Reworked BODS live-data acquisition around a shared account-level client: one operator-filtered SIRI-VM feed per unique operator is cached and reused by all configured stops, with route filtering performed locally.
- Added a 15-second shared operator cache, concurrent-request de-duplication and a minimum six-second interval between real upstream BODS requests to stay safely beyond the published five-second consumer guidance.
- Changed BODS HTTP error handling so only a genuine 401 triggers API-key reauthentication; 403 is reported as `access_forbidden` and 429 as `rate_limited` without incorrectly invalidating the configured key.
- Made the native **Next bus delay** numeric sensor unavailable when no live delay estimate exists, preserving the distinction between **0 min delay** and **no live delay measurement** and avoiding non-numeric numeric-sensor states.

## 0.5.0 — 2026-08-27

- Added an optional per-stop **Stop view** with **Departures**, **Arrivals**, and **Arrivals and departures** modes.
- Preserved **Departures** as the default so existing intermediate boarding stops keep their previous passenger-facing behaviour unless explicitly reconfigured.
- Added separate ordered `arrivals` and `departures` data for termini while keeping `Next bus`, walking guidance and `Leave now` tied to the next boardable departure.
- Added conservative live terminus states: **At stand** for a proven outbound origin journey at the stop, **Arrived** for a proven inbound destination journey at the stop, and **Approaching** for a live inbound terminating journey within five minutes.
- Incoming vehicles are never assumed to form a later outbound working; **At stand** is only shown after BODS/GTFS matching identifies the outbound origin journey itself.
- Added `previous_stop` to arrival rows from the ordered GTFS stop sequence, giving clearer local context such as **Haymarket Barras Bridge** instead of ambiguous generic journey origins such as `Bus Station`.
- Marked the large rolling `departures`, `arrivals`, and terminus attributes as unrecorded so they remain available live to dashboards and automations without exceeding Home Assistant Recorder's state-attribute size limit.
- Added a separate generic stock Home Assistant terminus Markdown card alongside the existing generic departure card.
- Added terminus documentation and a real Home Assistant Haymarket Bus Station example showing simultaneous **At stand**, **Approaching**, separate arrivals/departures and `previous_stop` presentation.
- Real-world beta validation completed with Arriva North East X14/X15/X16/X18 services at The Fairway and Haymarket Bus Station, including live **Approaching**, **Arrived**, **At stand**, conservative inbound/outbound vehicle linking, and Recorder regression testing.
- HACS, Hassfest and runtime/manifest version-sync validation passed before release.

## 0.4.2 — 2026-08-26

- Replaced the corrupted/truncated bus icon with a complete 256×256 transparent icon with safe padding so the full bus body and wheels remain visible across Home Assistant views, including Repairs.
- Replaced the packaged integration copy of the icon with the same byte-identical asset.
- Replaced the broken departure-card image with the approved working walking-guidance screenshot and restored the README to the PNG on `main`.
- Removed the malformed duplicate JPEG image from the repository.
- Binary asset uploads were verified by matching local and GitHub Git blob hashes.
- No ETA, GTFS matching, walking-time, configuration, entity or coordinator behaviour changes from 0.4.1.

## 0.4.1 — 2026-08-26

- Fixed the stop-device software version so it matches the released integration version instead of showing `0.4.0-beta.1`.
- Added a regression test requiring the runtime version constant and `manifest.json` version to match.
- Replaced the blank/incorrect departure-card image with the approved working walking-guidance card image.
- No ETA, matching, walking-time or configuration behaviour changes from 0.4.0.

## 0.4.0 — 2026-08-26

- Added a HACS-installable Home Assistant integration with config flow and multi-stop subentries.
- Added BODS SIRI-VM + BODS GTFS matching with route/operator-aware service selection.
- Added native sensors for next bus, route ETAs, scheduled/expected times, delay, timing state, walking guidance and diagnostics.
- Added configurable static walking time with `Leave by`, `Leave in` and `Leave now` passenger guidance.
- Added GTFS caching/refresh, BODS route-health reporting and stale-live-data handling.
- Added migration support for the earlier single-stop config-entry format.
- Added generic Home Assistant dashboard-card example and project documentation.

## 0.3.1 — 2026-08-25

- Added beta packaging/validation work for the initial custom integration.

## 0.3.0 — 2026-08-25

- Converted the earlier Fairway proof of concept into a multi-stop Home Assistant custom integration.

## Earlier development

The project began as a standalone Fairway/Morpeth BODS + GTFS proof of concept before being rebuilt as the current Home Assistant integration.