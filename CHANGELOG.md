# Changelog

## 0.4.2 — 2026-08-26

- Replaced the corrupted/truncated bus icon with a complete 256×256 transparent icon with safe padding so the full bus body and wheels remain visible in Home Assistant views.
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
