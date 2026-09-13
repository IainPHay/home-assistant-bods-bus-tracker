# Zone-exit catchable-bus notification

The v0.7 zone-exit blueprint turns the already-validated **Catchable bus** state into a reusable Home Assistant notification.

It deliberately does **not** recalculate which bus is reachable. BODS Bus Tracker decides catchability first using the effective routed/static walking time plus the per-stop **Catchable-bus safety margin**. The blueprint only sends a notification when the Catchable bus sensor reports `status: ok`.

## Blueprint

[`BODS Bus Tracker - Zone exit catchable bus notification`](blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml)

The automation triggers when a selected `person` leaves a selected Home Assistant `zone`.

Required inputs:

- traveller;
- origin zone;
- the BODS **Catchable bus** sensor for the boarding stop;
- a primary notification/announcement action.

Optional inputs:

- notification title;
- a second notification/announcement action.

## Why the blueprint consumes Catchable bus

The catchable sensor is the trusted boundary.

It has already applied:

- the current effective walking time;
- routed/static walking fallback;
- the configured safety margin;
- the passenger-facing expected departure time, falling back to the timetable when necessary;
- the full ordered departure sequence rather than only the dashboard's public 12-row list.

The blueprint therefore does not inspect the raw departure board, perform its own time threshold calculation, or add a second hidden margin.

If the sensor is unavailable or its status is anything other than `ok`, the automation does nothing. This prevents `walking_disabled`, `no_departures`, `none_in_window`, or other non-trusted states from being presented as a catchable journey.

## Notification variables

The blueprint prepares these variables before running the selected actions:

| Variable | Meaning |
| --- | --- |
| `bods_title` | Configured notification title. |
| `bods_message` | Ready-to-send passenger-facing summary. |
| `bods_route` | Catchable route. |
| `bods_destination` | Catchable destination/headsign where available. |
| `bods_expected` | Passenger-facing expected departure timestamp. |
| `bods_scheduled` | Published scheduled departure timestamp. |
| `bods_realtime` | Whether the selected departure has live tracking. |
| `bods_source` | BODS source, such as live or timetable. |
| `bods_timing_status` | Early/on-time/late/timetable status where available. |
| `bods_delay_minutes` | Passenger-facing delay value where available. |
| `bods_walking_minutes` | Effective walking duration used by catchability. |
| `bods_margin_minutes` | Explicit per-stop safety margin. |
| `bods_required_lead_minutes` | Walking + safety margin. |
| `bods_departure` | Privacy-safe catchable-departure summary mapping. |
| `bods_following_departure` | Privacy-safe following-departure summary mapping. |

A typical generated message is:

> Catchable: X18 to Newcastle — expected 19:51; scheduled 19:45 · 34 min away · live, late (6 min late). Walking: 5 min + 3 min margin (8 min required lead). Following: X18 to Newcastle — expected 20:51; scheduled 20:51 · timetable.

## Primary notification examples

### Modern notify entity

If the phone/device is available as a Home Assistant `notify` entity:

```yaml
- action: notify.send_message
  target:
    entity_id: notify.my_phone
  data:
    title: "{{ bods_title }}"
    message: "{{ bods_message }}"
```

### Companion App notify action

For installations that expose the phone-specific Companion App action:

```yaml
- action: notify.mobile_app_my_phone
  data:
    title: "{{ bods_title }}"
    message: "{{ bods_message }}"
```

The same pattern can be used for the optional second action, or the second action can call a script/announcement instead.

## Concrete automation example

After importing the blueprint, an automation can look like:

```yaml
alias: Bus options when leaving zone
description: >
  Tell the traveller which bus is already proven catchable when they leave
  the configured origin zone.
use_blueprint:
  path: IainPHay/home-assistant-bods-bus-tracker/bods_bus_tracker_zone_exit_catchable.yaml
  input:
    traveller: person.YOUR_TRAVELLER
    origin_zone: zone.YOUR_ORIGIN_ZONE
    catchable_bus_entity: sensor.YOUR_STOP_CATCHABLE_BUS
    notification_title: Bus options
    primary_notification_action:
      - action: notify.mobile_app_YOUR_PHONE
        data:
          title: "{{ bods_title }}"
          message: "{{ bods_message }}"
    secondary_notification_action:
      - action: notify.mobile_app_SECOND_PHONE
        data:
          title: "{{ bods_title }}"
          message: "{{ bods_message }}"
```

The stored `use_blueprint.path` can vary depending on how the blueprint is imported; Home Assistant will normally populate it automatically when the automation is created from the UI.

## Safety-margin policy

The blueprint has **no separate safety-margin input**.

Set the desired margin on the BODS stop configuration instead. The Catchable bus sensor exposes:

```yaml
walking_minutes: 5
margin_minutes: 3
required_lead_minutes: 8
```

That keeps one source of truth and prevents an automation from silently applying different catchability rules from the integration.

## Live and timetable operation

The same blueprint works when BODS has a live matched vehicle and when the integration is using timetable fallback.

The message preserves:

- expected and scheduled departure time;
- live/timetable source;
- early/on-time/late state where available;
- delay value where available;
- walking duration;
- explicit margin;
- required lead time;
- the following departure.

The blueprint never changes BODS ETA/matching or walking decisions.

## Privacy

The blueprint reads only the Catchable bus sensor and the selected Home Assistant zone/person trigger.

It does not copy person/device coordinates into BODS, does not access routing-provider credentials, and does not use the private full departure scratch list. The catchable and following-departure mappings are the same privacy-safe summaries exposed by the integration.

## Beta validation checklist

Before promoting the blueprint to stable v0.7:

1. Import the blueprint on a real Home Assistant installation.
2. Configure a person, origin zone, Catchable bus sensor and primary phone notification.
3. Confirm a zone exit with `status: ok` sends exactly one notification.
4. Compare route, destination, expected/scheduled times, walking time, margin and following departure with the Catchable bus entity.
5. Validate a live delayed journey.
6. Validate timetable fallback.
7. Confirm `walking_disabled`, `no_departures` and `none_in_window` do not send a misleading notification.
8. Validate the optional second recipient.
9. Confirm normal Next bus / Leave by / Leave in / Leave now behaviour is unchanged.
