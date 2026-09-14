# Changelog

## 0.7.0-beta.4 — in development

### Zone-exit catchable-bus notifications

- Added a reusable Home Assistant automation blueprint that triggers when a selected `person` leaves a selected `zone`.
- The blueprint consumes the native **Catchable bus** sensor as the trusted source of truth and does not recalculate catchability, ETA, routed/static walking, or the safety margin in YAML.
- Added one required primary notification/announcement action and an optional second action.
- Exposes a ready-to-send `bods_message` plus structured `bods_*` variables for custom Companion App, notify-entity, Alexa, script, or other Home Assistant actions.
- Notification content preserves route, destination, expected/scheduled departure time, live/timetable state, timing/delay detail, effective walking time, explicit safety margin, required lead time, and the following departure.
- Non-trusted Catchable bus states do not produce a notification.
- Added dedicated setup/documentation, a concrete automation example, and regression-policy tests that guard against recreating catchability from raw departure lists or local time arithmetic.
- Controlled real Home Assistant execution validated Catchable bus → blueprint variables → Companion App notify service using timetable fallback; message formatting was then cleaned up and re-tested successfully.
- Genuine physical zone-exit triggering and confirmation of receipt on the target phone remain the final live gate before beta.4 publication.

### Integration Quality Scale hardening

- Added targeted edge-path regression tests for authentication probing, shared live-feed caching/rate spacing, catchability, GTFS cache validation, stop search ranking, SIRI warning paths and conservative live/GTFS matching guards.
- `config_flow.py` now measures **100%** line coverage.
- Every integration Python module now measures **greater than 95%** line coverage.
- Overall integration line coverage is now **100.00%** with **191 tests passing**.
- The final defensive paths covered include legacy-device migration, translated GTFS update failure, successful SIRI warning collection, malformed GTFS trip handling, stale realtime candidates, temporary-file cleanup failures and the hourly unchanged-fingerprint cache path.
- CI now enforces **100% overall line coverage**, **100% for `config_flow.py`**, and **100% for every integration Python module**.
- Added `QUALITY_SCALE.md` as a durable Bronze/Silver/Gold/Platinum rule-by-rule evidence map.

## 0.7.0-beta.3 — 2026-09-13

### Diagnostics/privacy hardening

- Fixed a real beta.2 diagnostics leak where the private full departure scratch list `_departures_for_guidance` could survive when walking guidance was disabled and therefore appear in Home Assistant diagnostics.
- Catchable processing now removes the private full departure sequence before every return path, including `walking_disabled`.
- Diagnostics independently strip `_departures_for_guidance` as a defence-in-depth safeguard.
- Added regression coverage for walking-disabled cleanup and diagnostics removal of private guidance state and coordinates.
- The issue did **not** expose `person` / `device_tracker` coordinates or routing-provider credentials; the leaked rows were internal departure candidates and could include trip IDs.
- Catchable summaries remain restricted to the intended automation-safe fields and still exclude live vehicle coordinates and trip IDs.
- Real beta.2 validation confirmed positive catchability, explicit-margin rejection, walking-disabled/arrivals-only suppression, and static fallback feeding catchability.
- CI policy now avoids duplicate push + pull-request validation runs on feature branches; release tags, `main`, pull requests, nightly checks and manual validation remain covered.

## 0.7.0-beta.2 — 2026-09-13

### Catchable-bus state

- Added a derived **Catchable bus** sensor for departure/combined stop views.
- The sensor identifies the first departure whose expected departure time is at or after the current time plus the effective walking time plus an explicit per-stop safety margin.
- Added configurable **Catchable-bus safety margin**, default 0 minutes, range 0–30 minutes.
- The margin is deliberately explicit rather than hidden inside the calculation.
- Live delay can make a previously unreachable journey catchable because the calculation uses the same passenger-facing expected time already produced by BODS.
- Exposes the immediately following departure as a fallback/reference for automations.
- Catchability is downstream of the existing ETA/matching engine and never changes Next bus, live matching or timetable ordering.
- Catchable state is disabled when walking guidance is disabled and is not produced for Arrivals-only views.
- Catchable summaries intentionally exclude live vehicle coordinates and trip IDs.
- The calculation uses the complete ordered departure set internally while preserving the established 12-row public dashboard list.

## 0.7.0-beta.1 — in development

v0.7 starts from the stable v0.6.0 runtime and keeps the conservative BODS/GTFS matching policy unchanged while building higher-level routing/provider and automation capabilities.

### Provider-portability foundation

- Expose the monitored stop's public GTFS `latitude` and `longitude` inside the existing **Next bus** `stop` attribute when timetable metadata are available.
- Keep stop coordinates separate from traveller/person coordinates: only the public bus-stop location is exposed.
- This makes it easier to configure HERE or alternative Home Assistant routing providers without manually looking up the boarding-point coordinates.
- Routed walking remains provider-neutral: BODS Bus Tracker still consumes a Home Assistant duration sensor rather than storing third-party routing credentials or calling a provider directly.

### Development direction

- Alternative routing providers are being evaluated before one is recommended for v0.7. The previously available OpenRouteService HACS custom component is currently unmaintained, so it is not being adopted blindly as the reference path.
- Catchable-bus notifications and boarding/journey inference remain later v0.7 work and will only be promoted to trusted automations after their state logic is validated.

## 0.6.0 — 2026-09-13

Stable v0.6 consolidates the beta.2–beta.7 work into one release focused on routed walking guidance, multi-stop efficiency, Home Assistant quality/lifecycle hardening, and more resilient BODS authentication handling.

### Routed dynamic walking

- Added optional provider-neutral routed walking time per stop using an existing Home Assistant duration sensor.
- Retained the configured static walking time as an automatic fallback for missing, unavailable, stale, invalid or excessive routed values.
- Added **Leave by**, **Leave in** and **Leave now** support for the effective routed walking duration without changing ETA/matching logic.
- Added configurable **Maximum routed walking time** per stop, range 1–1440 minutes, with a backward-compatible default of 120 minutes.
- Added a self-clearing Home Assistant Repair when a configured routed walking sensor has genuinely been deleted or renamed.
- Diagnostics do not copy routing-provider credentials or person/device coordinates.

### Shared BODS live feed and authentication resilience

- Reworked live acquisition around one shared operator-level SIRI-VM feed reused by all configured stops.
- Added a 15-second shared cache, concurrent request de-duplication and at least six seconds between real upstream request starts.
- Route filtering is performed locally after the shared operator response is received.
- HTTP 429 remains rate-limited fallback and ordinary HTTP 403 remains access-forbidden fallback rather than forcing reauthentication.
- Added handling for BODS' real invalid-token behaviour: an explicit `{"detail":"Invalid token."}` response is treated as authentication failure.
- Ambiguous vehicle-feed 403 responses are confirmed with a minimal secondary token probe before Home Assistant reauthentication is triggered.
- Initial/reauth API-key validation now uses a minimal BODS dataset request.

### Faster GTFS preparation and reconfiguration

- Stops in the same BODS region now share one parsed GTFS index built from the union of configured services.
- Added a persistent JSON parsed-index cache keyed by GTFS fingerprint, service date, exact service set and schema version.
- Normal same-day restarts can restore the parsed timetable from disk instead of rescanning the regional `stop_times.txt`.
- Optimised stop reconfiguration by pre-filtering raw `stop_times.txt` lines before CSV parsing while preserving exact stop matching and quoted CSV semantics.
- Live validation reduced The Fairway reconfigure flow to about seven seconds.

### Home Assistant quality and lifecycle hardening

- Added Home Assistant-native tests using `pytest-homeassistant-custom-component` with a CI-enforced 95% coverage floor.
- Added strict Home Assistant-style mypy validation.
- Added HACS, Hassfest, version-sync and GTFS cache-policy CI gates.
- Added translated entities/states/errors, icon translations, device classes and appropriate entity categories/default-disabled diagnostics.
- Added clean unload cancellation/cache cleanup and persistent GTFS cache removal when the integration is deleted.
- Bus stops are represented as logical Home Assistant service devices with stale-device cleanup.
- Added a generic **Leave now notification** automation blueprint.
- Quality-scale tracker marks all applicable Bronze, Silver, Gold and Platinum rules complete or explicitly exempt; as a custom integration this should be described as quality-scale aligned / Platinum-equivalent, not an official Home Assistant Core tier.

### Validation

- 151 Home Assistant-native tests.
- 95.59% overall integration coverage on the beta.7 release candidate.
- HACS validation passed.
- Hassfest passed.
- Runtime/manifest version-sync passed.
- GTFS cache-policy validation passed.
- Strict mypy passed.
- Real Home Assistant testing covered The Fairway and Haymarket Bus Station, including natural location-driven HERE walking time, static fallback/recovery, terminus arrivals/departures, live/timetable coexistence, diagnostics redaction, transient live-feed fallback and recovery.

## 0.6.0-beta.7 — 2026-09-12

- Fixed a real BODS authentication edge case discovered during beta.6 validation: BODS can return HTTP 403 for an invalid API token rather than HTTP 401.
- The shared live-feed client now keeps ordinary 403 responses as `access_forbidden`, but performs a minimal secondary BODS token probe when a vehicle-feed 403 is ambiguous.
- If BODS explicitly reports `{"detail":"Invalid token."}`, the response is classified as `authentication_failed` so Home Assistant can start the normal reauthentication flow.
- Plain 403 access/WAF responses remain distinct and do not trigger a misleading reauthentication prompt.
- Initial/reauth API-key validation now uses a minimal dataset request and preserves the explicit invalid-token signal.
- Added regression coverage for explicit invalid-token payloads, ambiguous vehicle-feed 403s confirmed by a secondary token probe, and config-flow invalid-auth mapping.


## 0.6.0-beta.6 — 2026-09-11

- Made the routed-walking safety ceiling configurable per bus stop instead of hard-coding 120 minutes.
- Existing stops remain backward compatible and default to **120 minutes** until reconfigured.
- Added **Maximum routed walking time** to add/reconfigure flows, allowing values from 1 to 1440 minutes.
- Routed durations above the configured limit continue to use the static fallback exactly as before.
- Exposed `walking_max_dynamic_minutes` on the Next bus attributes for transparent diagnostics.
- Added regression coverage proving the default 120-minute ceiling is retained and that a higher configured limit can accept a longer provider duration.


## 0.6.0-beta.5 — 2026-09-11

- Fixed a release-blocking Home Assistant reconfigure-flow timeout found during beta.4 testing.
- Optimised single-stop GTFS service discovery by pre-filtering raw `stop_times.txt` lines for the target stop before invoking the CSV parser.
- Preserves exact CSV column matching and the full set of services available at the stop; this is a performance optimisation only and does not restrict reconfiguration choices.
- Added regression coverage for exact stop matching, quoted stop IDs and false-positive target text in other GTFS columns.
- Live Home Assistant validation confirmed The Fairway reconfiguration now opens in about 7 seconds instead of timing out.
- Completed the routed-walking missing-source Repair test: a deleted configured source falls back to the static walking time, raises the translated Repair, and self-clears when routed walking is disabled/corrected.
- Full v0.6 beta history and stable-release criteria are recorded in [`V0.6_VALIDATION.md`](V0.6_VALIDATION.md).


## 0.6.0-beta.4 — 2026-09-11

- Added a pure GTFS parsed-index cache-validation policy and automated regression tests.
- Cache reuse is now explicitly tested to require an exact match for the GTFS file fingerprint, service date, configured service set and cache schema.
- Added a dedicated CI job for GTFS cache invalidation policy tests.
- Added a Home Assistant-native test harness using `pytest-homeassistant-custom-component`, covering parent configuration, reauthentication, stop subentries, reconfiguration, setup/unload/removal, Repairs, diagnostics, entities and live-feed resilience.
- Added synthetic GTFS and SIRI-VM fixtures that exercise real ZIP/CSV/XML parsing, service calendars, stop/service discovery, trip indexing, live matching, delay projection and timetable-fallback health states without external network dependencies.
- Added explicit tests for the shared BODS operator feed, including cache reuse, in-flight de-duplication, 401/403/429 classification, timeout/connection handling and unload cancellation.
- Added entity-level tests for service-device grouping, translated entity keys, diagnostic defaults, device classes, delay availability semantics and diagnostics redaction.
- Added an enforced CI coverage floor of 95 percent; the beta.4 release candidate measures 96 percent overall with configuration-flow coverage at 100 percent.
- Added a Home Assistant-style strict mypy CI gate and resolved all strict-typing findings across the integration; all 15 runtime source files now pass.
- Updated the repository quality-scale tracker so every applicable Bronze, Silver, Gold and Platinum rule is marked complete, with non-applicable rules explicitly documented as exempt.
- These quality changes do not alter the live-to-GTFS ETA matching policy; they primarily add automated proof around the existing beta.3/beta.2 runtime behaviour.

## 0.6.0-beta.3 — 2026-09-11

- Reworked timetable preparation so all stops in the same BODS region share one parsed GTFS service index instead of independently scanning the regional `stop_times.txt` file.
- Builds the shared index from the union of configured services for that region, then gives each stop a lightweight filtered view; ETA, matching and stop-view behaviour remain unchanged.
- Added a persistent, non-pickle JSON parsed-index cache keyed to the exact GTFS file fingerprint, service date and configured service set. Normal same-day Home Assistant restarts can therefore restore parsed trips from disk instead of rescanning the regional GTFS archive.
- Added GTFS index diagnostics including initial/last source (`rebuilt`, `disk` or `memory`), preparation time, shared service/trip counts and generation number.
- The first beta.3 startup may still need one full regional parse to create the persistent cache; subsequent restarts with unchanged GTFS/date/services should be substantially faster.

## 0.6.0-beta.2 — 2026-09-11

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

- Added optional per-stop walking time configuration.
- Added Leave by and Leave in sensors derived from the already-calculated next-bus expected time.
- Added a Leave now binary sensor for Home Assistant automations.
- Added optional walking guidance to the generic dashboard card.
- Refined the generic dashboard card to five departures, left-aligned due information, red late values, `+N later departures`, and a one-line tracker footer.
- Added the approved real Home Assistant walking-guidance screenshot to the README.
- Walking guidance is post-processing only and does not alter the ETA/matching engine.
- Real-world tested against live Arriva North East services and cross-checked with the operator app.

## 0.3.2 — 2026-08-26

- Documentation/packaging-only release; no ETA, matching, configuration or runtime behaviour changes from 0.3.1.
- Updated the packaged README so HACS renders the Version and License badges correctly from the release tag.
- Updated packaged screenshot links to absolute GitHub raw URLs so screenshots render correctly inside HACS.
- Preserved the current preferred public README wording while updating the displayed version to 0.3.2.

## 0.3.1 — 2026-08-25

- Prepared 0.3.1 as the first public HACS-compatible beta repository with expanded documentation, screenshots and issue templates. Integration behaviour remains 0.3.1.

- Added passenger-friendly live timing states: `early`, `on_time`, `late`, with `timetable` for non-live departures.
- Added a **Next bus timing** entity for automations and dashboards.
- Added `raw_delay_minutes`, `timing_status`, `stop_role` and `prediction_clamped` attributes to live departure data.
- When the monitored stop is the **origin** of a journey, an early-running vehicle can no longer move the predicted departure before the published timetable. The raw early-running estimate is retained for diagnostics/status while the passenger-facing expected departure is clamped to the scheduled departure.
- Intermediate and destination stops continue to preserve genuine early-arrival predictions.
- Updated the generic dashboard card to render friendly wording such as `3.2 min early`, `19.9 min late`, `On time`, and `held to timetable` instead of signed delay numbers.
- Preserved the 0.3 multi-stop/config-subentry architecture and the existing live-to-GTFS matching engine.

## 0.3.0 — 2026-08-25

- Reworked configuration around Home Assistant **config subentries**.
- A single parent BODS account now stores the API key once and can own multiple monitored bus stops.
- Each stop has independent region, service selection and polling interval configuration.
- Each stop is represented by its own Home Assistant device and entity set.
- Added stop-subentry add/reconfigure/remove support using Home Assistant's native configuration UI.
- Added automatic migration from 0.1/0.2 one-stop entries to the new account + stop-subentry model.
- Migration preserves the legacy stop device identifier and entity unique IDs so existing entity IDs/history can survive the upgrade.
- Shared BODS-key reauthentication now applies to all configured stops.
- Diagnostics now report all stop subentries while continuing to redact the API key and vehicle coordinates.
- Preserved the 0.2 ETA/matching engine; Morpeth captured-data regression remains 15/15 exact live-to-GTFS matches.

## 0.2.0 — 2026-08-25

- Added stop search by **stop name**, **ATCO code** or **NaPTAN/SMS code** inside a selected BODS region.
- Added automatic BODS region detection for exact stop codes; region attempts are ordered using the Home Assistant installation location to avoid unnecessary GTFS downloads in the common case.
- Added a stop-selection step when a name search returns multiple boarding points.
- Added service reconfiguration without deleting/re-adding the tracker.
- Added BODS API-key reauthentication flow and automatic reauth trigger when all selected live feeds reject the key.
- Enriched the **Next bus** entity with generic departure-board attributes: ordered departures, tracker update time, data status, live vehicle count, GTFS matches and stop details.
- Added a generic stock Home Assistant Markdown departure-board card requiring only the tracker's **Next bus** entity ID.
- Preserved the 0.1 ETA/matching engine; Morpeth regression remains 15/15 exact live-to-GTFS matches.

## 0.1.0 — 2026-08-25

- First native Home Assistant beta.
- BODS API key, region, ATCO stop and service selection through config flow.
- Regional GTFS cache, SIRI-VM polling, GPS-based delay estimation and timetable fallback.
- Native sensors and diagnostics.
