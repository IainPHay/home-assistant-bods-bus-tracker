# Terminus arrivals and departures card

The terminus view is designed for stops where arrivals and departures are genuinely different passenger events, such as bus stations and route termini.

## Stop view setting

Reconfigure a monitored stop and choose **Stop view**:

- **Departures** — the default. This preserves the normal BODS Bus Tracker boarding-time behaviour and is recommended for ordinary intermediate stops.
- **Arrivals** — shows journeys reaching the monitored stop. Walking guidance is disabled because there is no boardable departure selected.
- **Arrivals and departures** — intended for termini. The integration exposes separate arrival and departure lists while `Next bus`, `Leave by`, `Leave in` and `Leave now` remain tied to the next boardable departure.

Existing stops which pre-date this feature continue to behave as **Departures** until explicitly reconfigured.

## Terminus state

When live vehicle and matched GTFS journey data support it, the integration can expose:

- **At stand** — a live vehicle has been matched to an outbound journey which originates at the monitored stop and its reported position is at the stop.
- **Arrived** — a live vehicle has been matched to an inbound journey which terminates at the monitored stop and its reported position is at the stop.
- **Approaching** — a live inbound terminating journey is within five minutes of the stop but is not yet at the stop.

Arrival rows also expose `previous_stop`, derived directly from the ordered GTFS stop list. The stock terminus card prefers this for arrival context because generic journey origins such as `Bus Station` can be ambiguous. For example, a Haymarket arrival can be shown as **previous stop Haymarket Barras Bridge** rather than incorrectly implying that Barras Bridge is the journey origin.

An arriving vehicle is **not** assumed to form a later outbound journey. The integration only labels a vehicle **At stand** after BODS/GTFS data identify that vehicle on the outbound origin journey itself. This deliberately avoids inventing vehicle duty links which BODS SIRI-VM may not supply.

## Recorder behaviour

The native **Next bus** entity exposes rich rolling `departures`, `arrivals` and terminus attributes for live dashboards and automations. At busy stops this payload can exceed Home Assistant Recorder's state-attribute size limit.

From `0.5.0`, these large transient attributes remain fully available in the live Home Assistant state machine but are marked unrecorded. This prevents Recorder size warnings and unnecessary database growth while the integration's normal small state sensors continue to be recorded.

## Generic terminus card

The repository includes the full generic stock Home Assistant Markdown card in:

- [`example_terminus_card.yaml`](example_terminus_card.yaml)

It is intended for a stop configured as **Arrivals and departures**.

Replace both occurrences of:

```text
sensor.YOUR_NEXT_BUS_ENTITY
```

with the native **Next bus** entity ID belonging to the configured terminus.

The card includes:

- **At stand**, **Arrived** and **Approaching** status when live data justify them;
- separate departures and arrivals boards;
- `previous_stop` context for arrivals;
- walking guidance for the next boardable departure when configured;
- live/timetable timing, early/late information and tracker health.

For an ordinary boarding stop, use the separate generic departure card instead:

- [`example_dashboard_card.yaml`](example_dashboard_card.yaml)
- [`DASHBOARD_CARD.md`](DASHBOARD_CARD.md)

## Real Home Assistant example

The following real `0.5.0-beta.2` Home Assistant test at Haymarket Bus Station shows the final `0.5.0` terminus presentation: simultaneous **At stand** and **Approaching** states, separate departures/arrivals, and `previous_stop` displayed as **Haymarket Barras Bridge**.

![BODS Bus Tracker terminus card at Haymarket Bus Station](https://github.com/user-attachments/assets/6884cf1b-d2ec-4d6c-9c12-7be9fae3f2ef)

## Real-world validation

Before the `0.5.0` release, the terminus behaviour was exercised live at Haymarket Bus Station with Arriva North East X14/X15/X16/X18 services. Testing confirmed:

- existing intermediate-stop behaviour remained unchanged at The Fairway;
- arrivals and departures were separated correctly;
- **Approaching** was observed on a live inbound journey;
- **Arrived** was captured on X18 vehicle 7719 at 118 m from the stop with `at_stop: true`;
- **At stand** was observed only after a live outbound origin journey was independently matched;
- an incoming vehicle was not falsely assumed to form a later outbound trip;
- `previous_stop` correctly resolved to **Haymarket Barras Bridge**;
- the Recorder oversized-attribute warning no longer occurred after the transient rich attributes were marked unrecorded.
