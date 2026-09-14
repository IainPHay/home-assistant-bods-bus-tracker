# BODS Bus Tracker for Home Assistant

[![Version](https://img.shields.io/badge/version-0.6.0-blue.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/releases/tag/v0.6.0)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.8%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Validate](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml/badge.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/actions/workflows/validate.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/LICENSE)

A native Home Assistant custom integration for English bus services using the UK Department for Transport **Bus Open Data Service (BODS)**.

It combines BODS live **SIRI-VM vehicle positions** with regional **GTFS timetables** to provide upcoming buses, live/scheduled status, estimated arrival or departure times, delay information, walking guidance, and per-service sensors directly in Home Assistant.

> **Pre-1.0 software.** Version 0.6.0 has been tested primarily with Arriva North East services around Morpeth and Newcastle. The integration is designed to be generic, but wider testing across operators and BODS regions is still welcome.

> **Important:** BODS does not require operators to publish stop-by-stop predicted arrival times in SIRI-VM. Where no operator prediction is available, this integration estimates delay from live vehicle position and the published timetable. It should be treated as passenger information, not a guaranteed departure time.

## What's new in v0.6

Version 0.6 is a substantial reliability and capability release rather than an ETA-algorithm rewrite. The core conservative BODS/GTFS matching policy remains intact while the surrounding data acquisition, walking guidance, startup/reconfigure performance and Home Assistant lifecycle handling have been hardened.

Key v0.6 changes:

- **Provider-neutral routed walking guidance** using a selected Home Assistant duration sensor, with static fallback and a configurable per-stop maximum routed duration.
- **Shared operator-level BODS live feeds** so multiple stops/services no longer create one upstream request per stop/route.
- **Shared persistent GTFS indexes** to avoid repeated regional timetable parsing across stops and normal same-day restarts.
- **Much faster stop reconfiguration** by avoiding a full CSV parse of every regional `stop_times.txt` row.
- **Home Assistant quality/lifecycle hardening** including clean unload, translated entities/errors, logical service devices, stale-device cleanup, Repairs, diagnostics redaction and strict automated validation.
- **Safer authentication handling** so a confirmed invalid BODS token can trigger reauthentication without treating every transient HTTP 403 as a credential failure.
- **151 Home Assistant-native tests** with a CI-enforced 95% coverage floor; the stable release candidate passed at **95.59%**.

If you are helping test v0.6 on another operator or BODS region, see [`TESTING.md`](TESTING.md).

For step-by-step setup guides, worked examples and extended troubleshooting, see the [BODS Bus Tracker Wiki](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki).

For the current Home Assistant Integration Quality Scale self-audit and rule-by-rule evidence, see [`QUALITY_SCALE.md`](QUALITY_SCALE.md).

## Screenshots

### Multiple stops under one BODS account

![BODS Bus Tracker showing multiple stop subentries](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/main/docs/images/multi-stop.png)

### Ordinary departure card with walking guidance

![Example Home Assistant departure card with walking guidance](https://raw.githubusercontent.com/IainPHay/home-assistant-bods-bus-tracker/main/docs/images/departure-card.png)

### Terminus arrivals and departures card

This real Home Assistant example from Haymarket Bus Station shows simultaneous **At stand** and **Approaching** states, separate arrivals/departures, and the new `previous_stop` context using **Haymarket Barras Bridge**.

![Example Home Assistant terminus arrivals and departures card](https://github.com/user-attachments/assets/6884cf1b-d2ec-4d6c-9c12-7be9fae3f2ef)

## Highlights

- Enter your **BODS API key once** and add multiple bus stops beneath the same account.
- Each monitored stop becomes its own Home Assistant device.
- Search stops by **name, ATCO code, or NaPTAN/SMS code** within a selected BODS region.
- Optional automatic region detection when an exact stop code is known.
- Discovers the route/operator combinations that actually call at the selected stop.
- Select only the services you want to monitor.
- Live vehicle positions are matched to the day's GTFS trips.
- Falls back cleanly to the published timetable when a live match is not yet available.
- Distinguishes **early**, **on time**, **late**, and **timetable-only** predictions.
- Prevents an early-arriving vehicle at a journey origin from being shown as departing before its published departure time.
- Per-stop **Departures**, **Arrivals**, or **Arrivals and departures** views.
- Terminus-aware live states including **At stand**, **Arrived**, and **Approaching** when BODS/GTFS data justify them.
- Arrival rows expose the previous GTFS stop for clearer local context at termini.
- Configurable live polling interval per stop.
- Optional per-stop walking guidance with **Leave by**, **Leave in** and automation-friendly **Leave now** entities, using either a static fallback or a routed Home Assistant travel-time sensor.
- Configurable per-stop maximum routed walking duration, with a backward-compatible 120-minute default and automatic static fallback for excessive, stale or unavailable provider values.
- Shared operator-level BODS live feeds with caching, in-flight de-duplication and request spacing to reduce upstream load across multiple stops.
- Shared and persistent GTFS indexes substantially reduce repeated startup/reconfigure parsing work.
- Confirmed invalid BODS tokens use Home Assistant's reauthentication flow, while ordinary 403 access failures remain timetable-fallback conditions rather than false credential failures.
- Rich live dashboard attributes are kept out of Recorder history to avoid oversized-attribute warnings at busy stops.
- Built-in diagnostics and downloadable Home Assistant diagnostics with API keys and vehicle coordinates redacted.
- A self-clearing Home Assistant Repair is raised when a configured routed walking-time entity is genuinely deleted or renamed.
- Two generic stock Home Assistant Markdown dashboard cards are included: one for ordinary departures and one for termini.

## Requirements

- Home Assistant **2026.8 or newer**.
- HACS for HACS installation, or manual access to Home Assistant's `custom_components` directory.
- A free BODS API key from the Department for Transport.
- The target timetable/service must be published through BODS.

BODS covers bus services in **England**. Availability and completeness of live vehicle data depend on what each operator publishes.

BODS Bus Tracker does not integrate physical devices. Each configured boarding point is represented as a logical Home Assistant service device containing the entities for that monitored stop.

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

You can also open this repository directly in HACS with:

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
7. Choose the **Stop view**:
   - **Departures** for an ordinary boarding stop;
   - **Arrivals** for an arrival-only view;
   - **Arrivals and departures** for a terminus or bus station where the distinction is useful.
8. Optionally enter the **Static walking time to stop**. This remains the safe fallback for leave guidance.
9. To use routed walking time, enable **Use routed dynamic walking time** and select a Home Assistant **duration sensor**. The integration is provider-neutral: it reads the selected entity's state and does not require it to come from a specific routing integration.
10. The duration sensor must report a finite non-negative duration in **seconds (`s`)**, **minutes (`min`)** or **hours (`h`)**. HERE Travel Time has been live-validated with a dynamic `person` origin; other providers are compatible in principle when they expose equivalent duration semantics.
11. Optionally adjust **Maximum routed walking time**; the default is **120 minutes** and longer provider durations fall back to the static walking time. See [`DYNAMIC_WALKING.md`](DYNAMIC_WALKING.md).
12. For v0.7 catchable-bus guidance, optionally set the explicit **Catchable-bus safety margin**. It defaults to **0 minutes** and is added to the effective walking time when deciding which departure is realistically reachable.
13. Choose the live polling interval. **30 seconds** is recommended.

For a detailed HERE walkthrough, see [Setting up routed walking with HERE Travel Time](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki/Setting-up-HERE-Travel-Time). For provider-neutral compatibility guidance, see [Routed walking providers](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki/Routed-walking-providers).

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
- use different stop views;
- use different walking times;
- use different polling intervals.

Each stop appears as a separate Home Assistant device.

## Reconfiguring a stop

Use the stop subentry's **Reconfigure** action to change:

- selected services;
- stop view;
- polling interval;
- static walking time to the stop;
- optional routed dynamic walking time, its Home Assistant travel-time sensor, and the per-stop maximum routed walking duration;
- the explicit Catchable-bus safety margin used by v0.7 catchability and zone-exit notifications.

To track a different physical boarding point, add the new stop and remove the old one.

## Use cases

Typical ways to use BODS Bus Tracker include:

- **Local departure board** — show the next buses for a nearby boarding point, with live/timetable status and per-route departure times.
- **Leave-now automation** — use **Leave by**, **Leave in** and **Leave now** to trigger a phone, Alexa or dashboard notification when it is time to walk to the stop.
- **Zone-exit catchable-bus notification (v0.7 beta)** — when a person leaves a configured zone, notify them of the first departure already proven catchable by the native **Catchable bus** state plus the following departure.
- **Dynamic walking guidance** — combine a Home Assistant travel-time integration with a `person` or `device_tracker` so walking time changes with the user's current location while retaining a static fallback.
- **Terminus monitoring** — use **Arrivals and departures** to distinguish incoming buses, approaching arrivals and independently matched outbound vehicles at stand.
- **Service health monitoring** — use **Data status**, **Last update** and downloadable diagnostics to distinguish live BODS problems from timetable fallback.

## Automation example

Ready-to-import Home Assistant automation blueprints are included:

- [`BODS Bus Tracker - Leave now notification`](blueprints/automation/bods_bus_tracker_leave_now.yaml) — select a stop's **Leave now** binary sensor and choose any notification or announcement action to run when it turns on.
- [`BODS Bus Tracker - Zone exit catchable bus notification`](blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml) — v0.7 beta blueprint that triggers when a selected person leaves a selected zone and consumes the trusted native **Catchable bus** state rather than recreating ETA/walking logic in YAML.

The zone-exit blueprint exposes a ready-to-send `{{ bods_message }}` plus structured `bods_*` variables to a required primary notification action and an optional second action. The safety margin is configured once on the BODS stop and is not duplicated in the automation. See [`ZONE_EXIT_NOTIFICATION.md`](ZONE_EXIT_NOTIFICATION.md) and [`example_zone_exit_catchable_notification.yaml`](example_zone_exit_catchable_notification.yaml).

The blueprints are intentionally provider/notification neutral: they can call Companion App notifications, notify entities, Alexa announcements, scripts or other Home Assistant actions without putting provider credentials into BODS.

More worked automation examples are collected in the [Automation recipes Wiki page](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki/Automation-recipes).

For the complete v0.6 development and validation history, see [`V0.6_VALIDATION.md`](V0.6_VALIDATION.md).

## Stop views

### Departures

**Departures** is the default and is recommended for ordinary intermediate boarding stops. It preserves the established BODS Bus Tracker behaviour: `Next bus`, per-service sensors, walking guidance and the generic departure card all refer to boardable departures.

### Arrivals

**Arrivals** selects journeys reaching the monitored stop. Because there is no boardable departure selected, walking guidance is disabled in this mode.

### Arrivals and departures

**Arrivals and departures** is intended for termini and bus stations. It exposes separate ordered `arrivals` and `departures` lists while `Next bus`, `Leave by`, `Leave in` and `Leave now` remain tied to the next boardable departure.

When live data justify it, the terminus data can include:

- **At stand** — a live vehicle is independently matched to an outbound journey originating at the monitored stop and is physically at the stop.
- **Arrived** — a live inbound destination journey is physically at the terminus.
- **Approaching** — a live inbound terminating journey is within five minutes of the stop.

The integration deliberately does **not** assume that an incoming vehicle will form a later outbound journey. A vehicle is only shown as **At stand** after the outbound origin journey itself has been matched.

For arrival context, `previous_stop` is derived from the ordered GTFS stop list. This avoids relying on ambiguous generic journey origins such as `Bus Station` and can instead show a familiar local stop such as **Haymarket Barras Bridge**.

See [`TERMINUS_CARD.md`](TERMINUS_CARD.md) for more detail, or the [Terminus setup Wiki page](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki/Terminus-setup) for the extended walkthrough.

## Entities

Each configured stop creates a device containing the following entities.

| Entity | Purpose |
| --- | --- |
| **Next bus** | Main selected journey. In **Departures** / **Arrivals and departures** it remains the next boardable departure; in **Arrivals** it represents the next arrival. |
| **Next bus minutes** | Whole minutes until the selected expected arrival/departure. |
| **Next bus expected** | Timestamp of the current expected arrival/departure. |
| **Next bus scheduled** | Published timetable timestamp. |
| **Next bus delay** | Passenger-facing effective delay when live tracking is available. |
| **Next bus timing** | `early`, `on_time`, `late`, or `timetable`. |
| **Leave by** | Timestamp at which to start walking for the next boardable bus when walking time is configured. |
| **Leave in** | Minutes until the calculated leave-by time. |
| **Leave now** | Binary sensor that turns on when it is time to start walking; intended for automations. |
| **Catchable bus** | v0.7 derived state for the first departure reachable using effective walking time plus the explicit safety margin; exposes a privacy-safe selected departure and the following departure. |
| **Next <service>** | Next boardable departure for each selected service. |
| **Data status** | `ok`, `degraded`, or `scheduled_only`. |
| **Last update** | Last successful tracker update. |
| **Live vehicles** | Number of relevant live vehicle records received. |
| **GTFS matches** | Number of live vehicles successfully matched to timetable trips. |

### Useful attributes

The **Next bus** entity exposes ordered journey data for live dashboards and automations.

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

Typical arrival data can also include:

```yaml
event_type: arrival
stop_role: destination
origin: Bus Station
previous_stop: Haymarket Barras Bridge
at_stop: false
```

For a stop in **Arrivals and departures** mode, the **Next bus** entity can expose:

- `departures` — ordered boardable departures;
- `arrivals` — ordered terminating arrivals;
- `next_departure`;
- `next_arrival`;
- `terminus.at_stand_departures`;
- `terminus.arrived_vehicles`;
- `terminus.approaching_arrivals`.

When routed walking is configured, the same entity also exposes the effective walking decision and source health:

- `walking_minutes` — whole minutes currently used for leave guidance;
- `walking_mode` — `static`, `dynamic`, `static_fallback` or `disabled`;
- `walking_time_entity` — the selected Home Assistant duration entity;
- `walking_dynamic_minutes` — raw normalised routed duration when valid;
- `walking_max_dynamic_minutes` — configured per-stop acceptance ceiling;
- `walking_fallback` — whether static fallback is currently being used;
- `walking_source_status` — provider/entity health such as `ok`, `unavailable`, `stale`, `missing` or `invalid`;
- `leave_by`, `leave_in_minutes` and `leave_now` — calculated from the effective walking time and the next boardable departure.

The large rolling journey lists are intentionally marked as **unrecorded**. They remain available live to cards, templates and automations but are not written into Recorder history, avoiding Home Assistant's state-attribute size limit at busy stops.

`stop_role` can be `origin`, `intermediate`, or `destination`.

## Early departures and journey origins

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
| `scheduled_only` | All live requests failed; timetable journeys remain available. |

A service can show **Timetable** while overall data status is `ok`. This simply means BODS is healthy but that particular journey has not yet been matched to a live vehicle.

## Generic dashboard card examples

Two complete generic stock Home Assistant Markdown card examples are included. Neither requires a custom frontend card.

| Use case | Generic YAML | Documentation |
| --- | --- | --- |
| Ordinary boarding stop / departure board | [`example_dashboard_card.yaml`](example_dashboard_card.yaml) | [`DASHBOARD_CARD.md`](DASHBOARD_CARD.md) |
| Terminus / bus station with arrivals and departures | [`example_terminus_card.yaml`](example_terminus_card.yaml) | [`TERMINUS_CARD.md`](TERMINUS_CARD.md) |

Both examples use the same placeholder:

```yaml
entity_id:
  - sensor.YOUR_NEXT_BUS_ENTITY
```

and inside the template:

```jinja
{% set entity = 'sensor.YOUR_NEXT_BUS_ENTITY' %}
```

Replace **both** occurrences with the native **Next bus** entity ID for the stop you want to display.

The full generic code is kept in the two YAML files above so it can be copied directly into a Home Assistant **Markdown** card without hard-coded route numbers or stop names.

## Data updates and network behaviour

BODS Bus Tracker is a polling integration, but it deliberately avoids making one upstream BODS request for every route and stop.

- Each stop has a configurable coordinator interval; **30 seconds** is recommended.
- Stops sharing an operator reuse one shared operator-filtered BODS SIRI-VM response.
- Successful and failed operator results are cached for **15 seconds** and concurrent requests for the same operator are de-duplicated.
- Real upstream BODS requests are serialised with at least **6 seconds** between request starts, providing margin over the published five-second consumer guidance.
- If live BODS data are temporarily unavailable, timetable data remain usable and the integration reports `degraded` or `scheduled_only` instead of repeatedly failing the whole integration.
- Regional GTFS ZIP files are cached under `.bods_bus_tracker_cache/` inside the Home Assistant configuration directory and normally refreshed about every 24 hours.
- Stops in the same region share one parsed GTFS index. A date/feed/service-aware JSON index cache allows normal same-day Home Assistant restarts to avoid rescanning the regional `stop_times.txt` file.
- Routed dynamic walking time is read from an existing Home Assistant duration sensor; BODS Bus Tracker does not poll HERE, Google or another routing provider itself.
- A vehicle-feed 403 is not automatically treated as a bad credential. Only an explicit invalid-token result, including a confirming minimal token probe when needed, is promoted to Home Assistant reauthentication.

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

For a fuller recovery/authentication checklist, see [Troubleshooting live data](https://github.com/IainPHay/home-assistant-bods-bus-tracker/wiki/Troubleshooting-live-data).

### The stop is not found

- Check that the correct regional timetable was selected.
- Try the exact ATCO/NaPTAN stop code.
- Automatic region detection requires an exact stop code.

### The API key stops working

The integration supports Home Assistant's reauthentication flow. A confirmed invalid BODS token triggers reauthentication and updating the shared API key applies to all configured stops.

Ordinary HTTP 403 access failures are kept distinct from invalid credentials. If BODS is temporarily refusing live requests, the integration falls back to timetable data and can recover automatically without forcing a misleading reauthentication flow.

## Current limitations

- Tested most extensively with Arriva North East X14/X15/X16/X18 services in Northumberland/Tyneside.
- Name search is regional GTFS-based; postcode/geocoder search is not yet included.
- Exact-code automatic region detection may need to check multiple regional GTFS feeds.
- Incomplete operator SIRI aimed-time records are currently skipped.
- Historical learning and traffic/roadworks/Waze enrichment are intentionally not yet implemented.
- The integration cannot infer a vehicle's next duty unless BODS/GTFS independently identifies that outbound journey.
- This integration estimates ETAs from public data and cannot guarantee that a bus will operate or arrive/depart at the predicted time.

## Roadmap

v0.7 development is tracked in [issue #8](https://github.com/IainPHay/home-assistant-bods-bus-tracker/issues/8). Provider-neutral routed walking, native Catchable bus state and the zone-exit notification blueprint are now implemented in the beta branch; the next major functional stage is conservative boarding inference followed by expected-arrival notifications only after that state is proven reliable.

Other longer-term possibilities include broader matching when SIRI aimed-time fields are incomplete, locality/postcode stop search, historical route-segment learning and wider operator/region regression testing.

## Removing the integration

To stop monitoring only one boarding point, open **Settings → Devices & services → BODS Bus Tracker** and remove that **Bus stop** subentry. The other configured stops continue to use the shared BODS account.

To remove BODS Bus Tracker completely:

1. Open **Settings → Devices & services → BODS Bus Tracker**.
2. Use the integration menu to delete the BODS Bus Tracker config entry.
3. Home Assistant unloads the sensor platforms, cancels outstanding BODS live-feed work and removes the integration's persistent GTFS/index cache.
4. If you installed the custom integration through HACS and no longer want the code installed, remove **BODS Bus Tracker** from HACS afterwards.

Removing the Home Assistant config entry does not revoke or delete the API key from your BODS account.

## Reporting problems

Please open a GitHub issue and include:

- Home Assistant version;
- BODS Bus Tracker version;
- BODS region;
- stop ATCO code;
- affected route/operator;
- stop view and selected services;
- whether routed walking is enabled and, if relevant, the routing integration/entity type used;
- approximate date/time of the problem;
- downloaded Home Assistant integration diagnostics, where relevant.

**Do not post your BODS API key.** If a routing provider or person/device tracker is involved, also avoid posting provider credentials or precise personal-location data unless you have intentionally redacted it first.

For structured cross-region/operator testing, use the checklist and report template in [`TESTING.md`](TESTING.md).

## Data sources and attribution

This integration uses public transport data from the UK Department for Transport **Bus Open Data Service (BODS)**, including regional GTFS timetables and SIRI-VM vehicle-location feeds.

Data remains subject to the terms and licensing of the original data providers.

This project is an independent community integration and is **not affiliated with or endorsed by the Department for Transport, BODS, Home Assistant, HACS, or any bus operator**.

## License

Released under the [MIT License](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/LICENSE).
