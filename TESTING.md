# Testing BODS Bus Tracker v0.6

Thank you for helping test BODS Bus Tracker outside the original Northumberland/Tyneside validation area.

The most useful v0.6 feedback now is **cross-operator and cross-region behaviour**: does the integration install cleanly, find the correct stop/services, populate sensible timetable/live data, survive restarts, and behave correctly when live BODS data are incomplete?

Please test the released **v0.6.0** build rather than an old beta unless you have been specifically asked to reproduce a beta-only issue.

## Before you start

You need:

- Home Assistant **2026.8 or newer**;
- BODS Bus Tracker **v0.6.0**;
- a valid BODS API key;
- a bus stop in England whose timetable is published through BODS;
- ideally an operator/region not already covered heavily by the project's Arriva North East testing.

Do not share your BODS API key in an issue, screenshot, log excerpt or chat message.

## Minimum useful test

A basic test does not require routed walking or a terminus.

1. Install/update BODS Bus Tracker through HACS and restart Home Assistant.
2. Confirm **Settings → Devices & services → BODS Bus Tracker** shows version **0.6.0**.
3. Add a bus stop.
4. Record:
   - BODS region;
   - stop name;
   - ATCO/NaPTAN code;
   - operator and selected services;
   - stop view.
5. Confirm the expected services are available for selection.
6. Confirm the stop creates its own Home Assistant device and entities.
7. Check **Next bus**, **Next bus minutes**, **Next bus expected**, **Next bus scheduled**, **Next bus timing** and the per-service entities.
8. Check the diagnostic entities:
   - **Data status**;
   - **Live vehicles**;
   - **GTFS matches**;
   - **Last update**.
9. Leave the integration running through several normal updates.
10. Restart Home Assistant once and confirm the stop returns without needing to be configured again.

A journey may legitimately show **Timetable** while **Data status** is `ok`. That means the shared live feed is healthy but that particular journey has not yet been matched to a trustworthy live vehicle.

## Multi-stop test

If you can, add a second stop under the same BODS account.

Useful combinations include:

- two stops using the same operator;
- stops in different regions;
- stops using different operators;
- one ordinary boarding stop plus one terminus/bus station.

Confirm:

- the BODS API key is not requested again;
- each stop has its own Home Assistant device;
- each stop keeps its own services, view, polling interval and walking configuration;
- restarting Home Assistant restores all configured stops;
- one stop being timetable-only does not make another stop unusable.

v0.6 shares operator-level live data and regional GTFS indexes internally, so multi-stop testing is especially valuable.

## Reconfigure test

Use the stop's **Reconfigure** action and confirm the form opens normally.

Try changing one harmless setting, for example:

- selected services;
- stop view;
- static walking time;
- polling interval.

The Fairway validation case opens the reconfigure flow in roughly seven seconds after the v0.6 optimisation. Other regions may differ, but a long timeout or multi-minute wait is worth reporting.

## Stop-view / terminus test

For an ordinary intermediate boarding stop, **Departures** is normally the correct view.

If you have a genuine terminus or bus station, try **Arrivals and departures** and check that:

- arrivals and departures are separated;
- **Next bus** still means the next boardable departure;
- **At stand** only appears for an independently matched outbound journey at the stop;
- an incoming bus is not automatically assumed to form the next outbound journey;
- **Approaching** / **Arrived** are only shown when live data justify them;
- arrival rows may show `previous_stop` for local context.

Do not expect every operator/feed to provide enough live information for every terminus state.

## Static walking test

Set **Static walking time to stop** to a small non-zero value.

Confirm:

- **Leave by** and **Leave in** become available for the next boardable departure;
- **Leave now** becomes useful as the leave time is reached;
- walking guidance does not alter the selected bus time or live/timetable matching.

## Routed dynamic walking test — optional

This is optional because it needs a separate Home Assistant routing/travel-time entity.

BODS Bus Tracker is provider-neutral. It only needs a selected duration sensor whose state is:

- numeric;
- finite and non-negative;
- expressed in `s`, `min` or `h`.

HERE Travel Time was live-validated during v0.6 development. Other providers are welcome test cases if they expose equivalent duration semantics.

When testing routed walking, record:

- routing integration/provider;
- selected duration entity;
- unit of measurement;
- static fallback time;
- configured **Maximum routed walking time**.

Useful checks:

1. A valid duration produces `walking_mode: dynamic`.
2. A fractional duration rounds **up** for effective walking guidance.
3. A duration above the configured maximum falls back to the static value.
4. Temporary `unknown` / `unavailable` provider state falls back without breaking bus tracking.
5. When the provider becomes valid again, dynamic walking resumes without reconfiguring BODS.
6. If the configured entity is genuinely deleted/renamed, Home Assistant should raise the translated missing walking-time sensor Repair, which should self-clear when corrected or dynamic walking is disabled.

See [`DYNAMIC_WALKING.md`](DYNAMIC_WALKING.md) for the exact provider-neutral contract.

## Live-data fallback/recovery

BODS live data are not equally complete for every operator.

If **Data status** changes to `degraded` or `scheduled_only`:

- confirm timetable departures remain available;
- note the approximate time;
- do not immediately delete/re-add the integration;
- see whether live data recover automatically;
- check **Settings → System → Logs** for BODS Bus Tracker warnings.

v0.6 deliberately distinguishes a confirmed invalid API token from an ordinary/transient HTTP 403. Do not intentionally invalidate your working API key just to test reauthentication.

## Dashboard examples

The repository includes two stock Home Assistant Markdown-card examples:

- ordinary boarding stop: [`example_dashboard_card.yaml`](example_dashboard_card.yaml);
- terminus/bus station: [`example_terminus_card.yaml`](example_terminus_card.yaml).

These cards are optional. If you test them, replace both placeholder entity IDs with your stop's native **Next bus** entity.

## Diagnostics

When reporting an issue, Home Assistant integration diagnostics are usually the most useful attachment.

Download diagnostics from the BODS Bus Tracker integration/device UI if available and check the file before sharing it.

The integration is designed to redact:

- the BODS API key;
- live vehicle coordinates from downloadable diagnostics.

Routing-provider credentials and person/device coordinates should not be copied into BODS diagnostics because BODS only stores the selected duration entity ID, not the provider's route configuration.

Still review any diagnostic/log file yourself before posting it publicly.

## Useful bug report template

Copy this into a GitHub issue and fill in what you know:

```text
Home Assistant version:
BODS Bus Tracker version: 0.6.0
Installation method: HACS / manual

BODS region:
Stop name:
ATCO/NaPTAN code:
Operator:
Selected service(s):
Stop view: Departures / Arrivals / Arrivals and departures
Polling interval:

Static walking time:
Routed walking enabled: yes / no
Routing provider/integration:
Duration entity unit:
Maximum routed walking time:

Observed Data status:
Live vehicles:
GTFS matches:

Expected behaviour:

Observed behaviour:

Approximate date/time:

Did it recover without reconfiguration? yes / no / not applicable

Relevant log message(s):

Diagnostics attached: yes / no
```

## What is especially valuable

The project has already been exercised heavily with Arriva North East X14/X15/X16/X18 around Morpeth and Newcastle.

The most valuable new reports are therefore:

- another operator;
- another BODS region;
- an unusual stop layout;
- a terminus with useful live data;
- multiple stops/operators on one account;
- a different routed-walking provider;
- a live-feed outage that falls back and later recovers;
- a service whose SIRI data do not match the assumptions seen in the Arriva North East feed.

Please report both **successes and failures**. A short "v0.6 works on operator X / region Y / stop Z" report is genuinely useful evidence for broadening confidence beyond the original test area.
