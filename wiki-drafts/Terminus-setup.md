# Terminus setup

Use **Arrivals and departures** for stops where distinguishing inbound terminating journeys from outbound boardable journeys is useful.

## Important linking rule

BODS Bus Tracker deliberately does **not** assume that an incoming vehicle forms the next outgoing service.

A vehicle is labelled **At stand** only when an independently matched outbound live journey exists at the stop.

Incoming journeys may separately appear as:

- Approaching;
- Arrived.

This conservative rule is intentional and remains unchanged in v0.6.

## Mixed live/timetable rows

A terminus can have **Data status: OK** while an individual departure is still timetable-only.

That is not contradictory. It means the shared live feed is healthy, but that particular journey has not yet been matched confidently to a live vehicle.

For the full stock card example, see:

https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/TERMINUS_CARD.md
