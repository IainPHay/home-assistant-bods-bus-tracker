# BODS Bus Tracker for Home Assistant

[![Version](https://img.shields.io/badge/version-0.3.1-blue.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/releases/tag/v0.3.1)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Validate](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml/badge.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/LICENSE)

A native Home Assistant custom integration for English bus services using the UK Department for Transport **Bus Open Data Service (BODS)**.

It combines BODS live **SIRI-VM vehicle positions** with regional **GTFS timetables** to provide upcoming buses, live/scheduled status, estimated arrival or departure times, delay information, and per-service sensors directly in Home Assistant.

> **Beta software.** Version 0.3.1 has been tested primarily with Arriva North East services around Morpeth/Newcastle. The integration is designed to be generic, but wider testing across operators and BODS regions is still welcome.

> **Important:** BODS does not require operators to publish stop-by-stop predicted arrival times in SIRI-VM. Where no operator prediction is available, this integration estimates delay from live vehicle position and the published timetable. It should be treated as passenger information, not a guaranteed departure time.

## Screenshots

### Multiple stops under one BODS account

![BODS Bus Tracker showing multiple stop subentries](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/main/docs/images/multi-stop.png)

### Example departure card

![Example Home Assistant departure card](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/main/docs/images/departure-card.png)

## Highlights

- Native Home Assistant integration — **no MQTT broker or Raspberry Pi sidecar required**.
- Enter your **BODS API key once** and add multiple bus stops beneath the same account.
- Each monitored stop becomes its own Home Assistant device.
- Search stops by **name, ATCO code, or NaPTAN/SMS code** within a selected BODS region.
- Optional automatic region detection when an exact stop code is known.
- Discovers the route/operator combinations that actually call at the selected stop.
- Select only the services you want to monitor.
- Live vehicle positions are matched to the day's GTFS trips.
- Falls back cleanly to the published timetable when a live match is not yet available.
- Distinguishes **early**, **on time**, **late**, and **timetable-only** departures.
- Prevents an early-arriving vehicle at a journey origin from being shown as departing before its published departure time.
- Configurable live polling interval per stop.
- Built-in diagnostics and downloadable Home Assistant diagnostics with API keys redacted.
- Generic stock Home Assistant Markdown dashboard card included.

## Requirements

- Home Assistant **2026.8 or newer**.
- HACS for HACS installation, or manual access to Home Assistant's `custom_components` directory.
- A free BODS API key from the Department for Transport.
- The target timetable/service must be published through BODS.

BODS covers bus services in **England**. Availability and completeness of live vehicle data depend on what each operator publishes.

## Get a BODS API key

1. Create a free account at [Bus Open Data Service](https://data.bus-data.dft.gov.uk/account/signup/).
2. Sign in and obtain your API key from your BODS account.
3. Keep the key private. Home Assistant stores it in the integration config entry and diagnostics redact it.

## Installation with HACS

This repository is HACS compatible as a **custom integration repository**.

### Add the repository to HACS

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add:

   `https://github.com/IainPHay/home-assistant-bods-bus-tracker`

4. Select category **Integration**.
5. Install **BODS Bus Tracker**.
6. Restart Home Assistant.

Once the repository is public, this shortcut can also be used:

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=IainPHay&repository=home-assistant-bods-bus-tracker&category=integration)

After installation, continue with [Initial setup](#initial-setup).

## Manual installation

1. Download the repository.
2. Copy:

   `custom_components/bods_bus_tracker/`

   to:

   `/config/custom_components/bods_bus_tracker/`

3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **BODS Bus Tracker**.

## Initial setup

The integration uses one parent BODS account and one or more **Bus stop** subentries.

1. Add **BODS Bus Tracker** from **Settings → Devices & services**.
2. Enter your BODS API key.
3. Home Assistant opens the first **Add bus stop** flow.
4. Choose a BODS timetable region, or **Auto detect** when you already know the exact ATCO/NaPTAN stop code.
5. Search for the stop by name/code and choose the exact boarding point/direction.
6. Select the services you want to monitor.
7. Choose the live polling interval. **30 seconds** is recommended.

### Supported regional timetable feeds

- East Anglia
- East Midlands
- London
- North East
- North West
- South East
- South West
- West Midlands
- Yorkshire

Automatic region detection is intended for exact stop codes. Name searches require selecting a region first.

## Adding more stops

Open **Settings → Devices & services → BODS Bus Tracker** and add another **Bus stop**.

The BODS API key is shared, so it is not requested again. Additional stops can:

- be in different BODS regions;
- monitor different operators/routes;
- use different polling intervals.

Each stop appears as a separate Home Assistant device.

## Reconfiguring a stop

Use the stop subentry's **Reconfigure** action to change:

- selected services;
- polling interval.

To track a different physical boarding point, add the new stop and remove the old one.

## Entities

Each configured stop creates a device containing the following entities.

| Entity | Purpose |
| --- | --- |
| **Next bus** | Route/service of the next expected departure and the main departure attributes. |
| **Next bus minutes** | Whole minutes until the expected departure/arrival. |
| **Next bus expected** | Timestamp of the current expected arrival/departure. |
| **Next bus scheduled** | Published timetable timestamp. |
| **Next bus delay** | Passenger-facing effective delay when live tracking is available. |
| **Next bus timing** | `early`, `on_time`, `late`, or `timetable`. |
| **Next <service>** | Next departure for each selected service. |
| **Data status** | `ok`, `degraded`, or `scheduled_only`. |
| **Last update** | Last successful tracker update. |
| **Live vehicles** | Number of relevant live vehicle records received. |
| **GTFS matches** | Number of live vehicles successfully matched to timetable trips. |

### Useful attributes

The **Next bus** entity includes an ordered `departures` list, so a dashboard card does not need to know the route names in advance.

Typical departure attributes include:

```yaml
route: X15
operator: Arriva North East
minutes: 4
scheduled: "2026-08-25T15:14:00+01:00"
expected: "2026-08-25T15:33:00+01:00"
source: live
vehicle: "7716"
timing_status: late
delay_minutes: 19.0
raw_delay_minutes: 19.0
stop_role: intermediate
prediction_clamped: false
```

`stop_role` can be `origin`, `intermediate`, or `destination`.

## Early departures and terminuses

An important distinction is made between **vehicle progress** and a **passenger departure prediction**.

If a bus reaches the origin of its next journey early, the raw GPS estimate may indicate a negative delay. The integration retains that raw value for diagnostics, but it will **not predict that the bus departs before the timetable**.

For example:

```text
Scheduled departure: 20:48
Vehicle progress:     3.2 min early
Expected departure:   20:48
Timing status:        early
Held to timetable:    yes
```

At intermediate/destination stops, a genuine early-arrival estimate is retained.

## How the ETA estimate works

Many BODS SIRI-VM feeds provide vehicle positions but do not include `MonitoredCall` / `OnwardCalls` with stop-level predictions. The integration therefore uses the following approach:

1. Download the relevant BODS regional GTFS timetable.
2. Build the active trips for the selected stop/services for the current day.
3. Poll BODS SIRI-VM live vehicle data.
4. Match each usable live vehicle to its scheduled GTFS trip using route/operator, origin/destination and aimed timing information.
5. Project the GPS location onto the sequence of GTFS stop segments.
6. Compare live progress with scheduled progress to estimate the current delay.
7. Apply that delay to the selected stop.
8. Fall back to the published timetable when no trustworthy live match is available.

Malformed, stale, or ambiguous live records are ignored instead of replacing trusted timetable data.

## Data status

| State | Meaning |
| --- | --- |
| `ok` | All selected live feeds responded successfully. |
| `degraded` | One or more live requests failed while others succeeded. |
| `scheduled_only` | All live requests failed; timetable departures remain available. |

A service can show **Timetable** while overall data status is `ok`. This simply means BODS is healthy but that particular approaching journey has not yet been matched to a live vehicle.

## Dashboard card

A generic stock Home Assistant Markdown card is included in:

- [`example_dashboard_card.yaml`](example_dashboard_card.yaml)
- [`DASHBOARD_CARD.md`](DASHBOARD_CARD.md)

It reads the ordered `departures` attribute from a single **Next bus** entity, so it can be reused for any configured stop without hard-coding route numbers.

## Caching and network behaviour

- Live data defaults to a **30-second polling interval per stop**.
- Regional GTFS is cached under `.bods_bus_tracker_cache/` inside the Home Assistant config directory.
- GTFS is refreshed approximately every 24 hours.
- Multiple stops in the same BODS region share the cached timetable file.
- The integration communicates with Department for Transport BODS endpoints over the internet.

## Privacy and data handling

The integration sends only the requests required to retrieve public BODS timetable/live transport data.

- Your BODS API key remains in the Home Assistant config entry.
- Diagnostics redact the BODS API key.
- Vehicle GPS coordinates are not included in downloadable diagnostics.
- There is no external analytics or telemetry implemented by this integration.

## Troubleshooting

### A bus is shown as timetable-only

This can be normal. A journey may not appear in the live feed until shortly before/after leaving its origin. The integration uses the timetable until a reliable live vehicle match is available.

### A live vehicle is missing

Some operators publish incomplete SIRI records. Records missing key aimed-time fields are currently skipped rather than guessed.

Check the **Live vehicles**, **GTFS matches**, and **Data status** diagnostic entities. Home Assistant's downloadable integration diagnostics can also help when opening an issue.

### The stop is not found

- Check that the correct regional timetable was selected.
- Try the exact ATCO/NaPTAN stop code.
- Automatic region detection requires an exact stop code.

### The API key stops working

The integration supports Home Assistant's reauthentication flow. Updating the shared API key applies to all configured stops.

## Upgrading from 0.1 / 0.2

Version 0.3 introduced a shared account + multiple stop-subentry architecture.

Do **not** delete the existing integration before upgrading. Existing one-stop configurations are migrated automatically so that:

- the BODS API key becomes the shared account credential;
- the existing stop becomes the first bus-stop subentry;
- the existing device is moved to the subentry;
- legacy entity unique IDs are retained where possible to preserve entity IDs/history.

## Current beta limitations

- Tested most extensively with Arriva North East X14/X15/X16/X18 services in Northumberland/Tyneside.
- Name search is regional GTFS-based; postcode/geocoder search is not yet included.
- Exact-code automatic region detection may need to check multiple regional GTFS feeds.
- Incomplete operator SIRI aimed-time records are currently skipped.
- Historical learning and traffic/roadworks/Waze enrichment are intentionally not yet implemented.
- This integration estimates ETAs from public data and cannot guarantee that a bus will operate or arrive/depart at the predicted time.

## Roadmap

Development is intentionally paused at **0.3.1** while this version receives real-world testing.

Potential future work includes:

- broader matching when SIRI aimed-time fields are incomplete;
- locality/postcode stop search;
- historical route-segment travel-time learning;
- optional traffic/roadworks anomaly flags;
- wider operator/region regression tests.

## Reporting problems

Please open a GitHub issue and include:

- Home Assistant version;
- BODS Bus Tracker version;
- BODS region;
- stop ATCO code;
- affected route/operator;
- approximate date/time of the problem;
- downloaded Home Assistant integration diagnostics, where relevant.

**Do not post your BODS API key.**

## HACS validation

The repository includes GitHub Actions for:

- official HACS repository validation;
- Home Assistant Hassfest validation.

The repository also carries the HACS-relevant GitHub topics, including `home-assistant`, `hacs`, and `hacs-integration`.

HACS requires one integration under `custom_components`, the required manifest metadata, and a root `brand/icon.png`; this repository is structured accordingly.

## Data sources and attribution

This integration uses public transport data from the UK Department for Transport **Bus Open Data Service (BODS)**, including regional GTFS timetables and SIRI-VM vehicle-location feeds.

Data remains subject to the terms and licensing of the original data providers.

This project is an independent community integration and is **not affiliated with or endorsed by the Department for Transport, BODS, Home Assistant, HACS, or any bus operator**.

## License

Released under the [MIT License](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/LICENSE).
