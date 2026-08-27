# Terminus arrivals and departures card

> Beta documentation for `0.5.0-beta.2` on `feature/terminus-arrivals`.

The terminus view is designed for stops where arrivals and departures are genuinely different passenger events, such as bus stations and route termini.

## Stop view setting

Reconfigure a monitored stop and choose **Stop view**:

- **Departures** — the default. This preserves the existing BODS Bus Tracker boarding-time behaviour and is recommended for ordinary intermediate stops.
- **Arrivals** — shows journeys reaching the monitored stop. Walking guidance is disabled because there is no boardable departure selected.
- **Arrivals and departures** — intended for termini. The integration exposes separate arrival and departure lists while `Next bus`, `Leave by`, `Leave in` and `Leave now` remain tied to the next boardable departure.

Existing stops which pre-date this feature behave as **Departures** until explicitly reconfigured.

## Terminus state

When live vehicle and matched GTFS journey data support it, the integration can expose:

- **At stand** — a live vehicle has been matched to an outbound journey which originates at the monitored stop and its reported position is at the stop.
- **Arrived** — a live vehicle has been matched to an inbound journey which terminates at the monitored stop and its reported position is at the stop.
- **Approaching** — a live inbound terminating journey is within five minutes of the stop but is not yet at the stop.

Arrival rows also expose `previous_stop`, derived directly from the ordered GTFS stop list. The stock terminus card prefers this for arrival context because generic journey origins such as `Bus Station` can be ambiguous; for example an approaching service can be shown as having **previous stop Barras Bridge** rather than incorrectly implying that Barras Bridge is the journey origin.

An arriving vehicle is **not** assumed to form a later outbound journey. The integration only labels a vehicle **At stand** after BODS/GTFS data identify that vehicle on the outbound origin journey itself. This deliberately avoids inventing vehicle duty links which BODS SIRI-VM may not supply.

## Recorder behaviour

The native **Next bus** entity deliberately exposes rich rolling `departures`, `arrivals` and terminus attributes for live dashboards and automations. At busy stops this payload can exceed Home Assistant Recorder's state-attribute size limit. From `0.5.0-beta.2` those transient attributes remain fully available in the live state machine but are marked unrecorded, preventing Recorder size warnings and unnecessary database growth. The integration's normal small state sensors continue to be recorded.

## Dashboard card

`example_terminus_card.yaml` is a separate generic stock Home Assistant Markdown card for a stop configured as **Arrivals and departures**.

Replace both occurrences of:

```text
sensor.YOUR_NEXT_BUS_ENTITY
```

with the native **Next bus** entity ID belonging to the configured terminus.

The card includes a compact terminus-state summary, departures board, arrivals board, walking guidance for the next departure, and tracker status. Arrival displays prefer `previous_stop` where available, falling back to the journey origin otherwise.

The existing `example_dashboard_card.yaml` remains the recommended card for ordinary intermediate boarding stops.

## Beta test sequence

For `0.5.0-beta.2`, confirm an existing intermediate stop remains unchanged in **Departures** mode, verify the terminus arrival/departure split and `previous_stop` presentation, confirm Recorder no longer logs oversized attributes for the native **Next bus** entity, and compare live terminus states with the operator app/direct observation before the feature is merged.
