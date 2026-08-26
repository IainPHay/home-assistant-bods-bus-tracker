# Terminus arrivals and departures card

> Beta documentation for `0.5.0-beta.1` on `feature/terminus-arrivals`.

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

An arriving vehicle is **not** assumed to form a later outbound journey. The integration only labels a vehicle **At stand** after BODS/GTFS data identify that vehicle on the outbound origin journey itself. This deliberately avoids inventing vehicle duty links which BODS SIRI-VM may not supply.

## Dashboard card

`example_terminus_card.yaml` is a separate generic stock Home Assistant Markdown card for a stop configured as **Arrivals and departures**.

Replace both occurrences of:

```text
sensor.YOUR_NEXT_BUS_ENTITY
```

with the native **Next bus** entity ID belonging to the configured terminus.

The card includes a compact terminus-state summary, departures board, arrivals board, walking guidance for the next departure, and tracker status.

The existing `example_dashboard_card.yaml` remains the recommended card for ordinary intermediate boarding stops.

## Beta test sequence

For `0.5.0-beta.1`, first confirm an existing intermediate stop remains unchanged in **Departures** mode, then reconfigure a terminus as **Arrivals and departures** and compare the live arrival/departure state with the operator app and direct observation before the feature is merged.
