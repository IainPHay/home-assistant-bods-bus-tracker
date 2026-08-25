# BODS Bus Tracker 0.3.1 beta test

Version 0.3.1 is a behavioural refinement of the working 0.3 multi-stop build. The config-subentry architecture is unchanged.

## 1. Upgrade the working 0.3 installation

1. Replace `/config/custom_components/bods_bus_tracker/` with the 0.3.1 component.
2. Restart Home Assistant.
3. Do **not** delete/re-add the BODS Bus Tracker account or its stop subentries.

Expected:

- existing stop subentries/devices remain in place;
- existing entity IDs/history remain available;
- each stop reports software/firmware version **0.3.1**;
- a new **Next bus timing** entity appears on each stop device;
- existing timetable/live predictions continue updating normally.

## 2. Check ordinary live journeys

At an intermediate stop such as The Fairway:

- a bus running more than about one minute late reports `late`;
- a bus running more than about one minute early reports `early` and may have an expected time earlier than timetable;
- a bus within approximately ±1 minute reports `on_time`;
- timetable-only journeys report `timetable`.

The route sensor/Next bus attributes should include:

- `delay_minutes`;
- `raw_delay_minutes`;
- `timing_status`;
- `stop_role`;
- `prediction_clamped`.

## 3. Check an origin/terminus stop

Use the Haymarket subentry or another stop where a selected journey **originates**.

If a vehicle is physically early:

- `timing_status` should be `early`;
- `raw_delay_minutes` may be negative;
- `stop_role` should be `origin`;
- `prediction_clamped` should be `true`;
- **Next bus expected must not be earlier than Next bus scheduled**;
- passenger-facing `delay_minutes` should be `0.0` rather than a negative departure delay.

This deliberately distinguishes "vehicle reached the terminus early" from "the bus will depart early".

## 4. Generic card

Use `example_dashboard_card.yaml` with each stop's **Next bus** entity.

Expected display examples:

- `3.2 min early` rather than `-3.2 min`;
- `19.9 min late` rather than `+19.9 min`;
- `On time` for small live deviations;
- `3.2 min early · held to timetable` when an origin/terminus prediction is clamped.

## 5. Multi-stop regression

With both The Fairway and Haymarket configured:

- both continue updating independently;
- reconfiguring one stop does not change the other;
- the shared BODS key remains at the parent integration level.

## Regression reference

Original regression stop:

- region: North East
- ATCO: `3100Z199842`
- stop: The Fairway
- operator: Arriva North East / `ANUM`
- services: X14, X15, X16, X18

The captured 25 August 2026 dataset must continue to produce **15/15 exact live-to-GTFS matches**.
