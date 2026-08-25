# Generic dashboard card

BODS Bus Tracker exposes an ordered `departures` list on each stop's **Next bus** entity. The included Markdown card uses that one entity to build a compact departure board for any configured stop.

No HACS dashboard card or other frontend dependency is required.

## Install the card

1. Open the Home Assistant dashboard you want to edit.
2. Add a **Markdown** card.
3. Copy the contents of [`example_dashboard_card.yaml`](example_dashboard_card.yaml).
4. Replace **both** occurrences of:

   `sensor.YOUR_NEXT_BUS_ENTITY`

   with the entity ID for that stop's **Next bus** sensor.

For example:

`sensor.the_fairway_3100z199842_next_bus`

The exact entity ID depends on the stop name and Home Assistant's entity registry.

## What it displays

- Stop name.
- Next service and minutes due.
- Live versus timetable-only status.
- Expected time.
- Friendly timing status such as `3.2 min early`, `On time`, or `19.9 min late`.
- `held to timetable` when an early vehicle is at the origin of its next journey.
- Vehicle ID when a live match is available.
- Up to eight upcoming departures in expected-time order.
- Tracker/data health and number of approaching live-tracked services.
- Relative last-update age.

## Compatibility

The example deliberately uses safe dictionary access (`row.get(...)`) for optional departure attributes. This avoids a dashboard failure if an attribute is temporarily missing and also makes the card tolerant of departure data created by earlier 0.3.x versions.

## Example

![Example BODS Bus Tracker departure card](docs/images/departure-card.png)
