# Changelog

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
