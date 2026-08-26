# Generic dashboard card

BODS Bus Tracker exposes an ordered `departures` list on each configured stop's **Next bus** entity. The included Markdown card uses that one entity to build a compact departure board for any stop configured in the integration.

The repository example is deliberately generic: it contains no fixed ATCO code, route number or stop name. No HACS dashboard card or other frontend dependency is required.

## Install the card

1. In Home Assistant, open **Settings → Devices & services → BODS Bus Tracker**.
2. Open the bus stop you want to display.
3. Find that stop's **Next bus** entity and copy its entity ID.
4. Open the dashboard you want to edit and add a **Markdown** card.
5. Copy the contents of [`example_dashboard_card.yaml`](example_dashboard_card.yaml).
6. Replace **both** occurrences of:

   `sensor.YOUR_NEXT_BUS_ENTITY`

   with the entity ID copied in step 3.

The exact entity ID is created by Home Assistant from the configured stop and may differ between installations. Do not copy an entity ID from the documentation or another user's stop.

## What it displays

- Stop name from the configured BODS stop.
- The next service prominently, including minutes due.
- Live versus timetable-only status and destination when available.
- Expected departure/arrival time.
- Friendly timing such as `3.2 min early`, `On time`, or `19.9 min late`.
- Late-running values highlighted in red for quick recognition.
- `held to timetable` when an early vehicle is at the origin of its next journey.
- Vehicle ID for the headline service when a live match is available.
- Optional `Leave in` / `Leave now` guidance when a walking time is configured for the stop.
- The next five departures in a compact, left-aligned two-column table.
- A `+N later departures` indication when more services are available.
- A one-line tracker/data-health, live-tracked count and last-update footer.

## Why only five departures?

The integration normally exposes more than five departures in the `departures` attribute. The example deliberately shows only the first five so the card stays useful on a normal Home Assistant dashboard instead of becoming a full timetable page.

Users who want a longer board can change:

`departures[:5]`

to another value, but the five-row layout is the recommended default.

## Compatibility

The example uses safe dictionary access (`row.get(...)`) for optional departure attributes so missing live fields do not break the card. It reads the route, stop, destination and timing data from the selected **Next bus** entity rather than hard-coding any particular service or boarding point.

## Example

![Example BODS Bus Tracker departure card](docs/images/departure-card.png)
