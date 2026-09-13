# Automation recipes

BODS Bus Tracker exposes automation-friendly entities and attributes so Home Assistant can act on trusted bus state without putting notification logic inside the integration.

This page covers **v0.6 functionality that exists now**. More ambitious journey inference and zone-exit logic is planned for v0.7 and is deliberately not treated as trusted state yet.

## Leave-now notification blueprint

The repository includes a generic blueprint:

[BODS Bus Tracker - Leave now notification](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/blueprints/automation/bods_bus_tracker_leave_now.yaml)

It triggers when a stop's native **Leave now** binary sensor changes to `on`.

The blueprint does not hard-code a notification provider. Its action can be:

- a Home Assistant Companion App notification;
- an announcement;
- a script;
- multiple actions;
- any other normal Home Assistant action sequence.

## Import the blueprint

Home Assistant can import blueprints directly from GitHub.

1. Go to **Settings → Automations & scenes → Blueprints**.
2. Select **Import Blueprint**.
3. Use this URL:

   ```text
   https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/blueprints/automation/bods_bus_tracker_leave_now.yaml
   ```

4. Select **Preview**.
5. Finish the import.
6. Find **BODS Bus Tracker - Leave now notification** and select **Create automation**.
7. Choose the stop's **Leave now** binary sensor.
8. Configure the notification/announcement action.
9. Save the automation.

Home Assistant's current blueprint documentation is here:

https://www.home-assistant.io/docs/automation/using_blueprints/

## Simple phone notification

A typical action for the blueprint is a Companion App notification.

Replace the notify service with your own phone's service:

```yaml
action: notify.mobile_app_YOUR_PHONE
data:
  title: "Bus reminder"
  message: "It is time to leave for the bus."
```

On phones with a paired watch, whether the notification also appears on the watch is controlled by the phone/watch notification settings.

## Rich phone notification using the Next bus entity

If you want route and timing information in the message, a normal automation can read the BODS **Next bus** attributes.

Replace both entity placeholders with your own entities:

```yaml
alias: BODS - Leave now phone notification
description: Notify when BODS says it is time to walk to the stop.
triggers:
  - trigger: state
    entity_id: binary_sensor.YOUR_LEAVE_NOW_ENTITY
    to: "on"

conditions: []

actions:
  - variables:
      bods_entity: sensor.YOUR_NEXT_BUS_ENTITY
      departures: "{{ state_attr(bods_entity, 'departures') or [] }}"
      bus: "{{ departures[0] if departures else {} }}"

  - action: notify.mobile_app_YOUR_PHONE
    data:
      title: >-
        {% if bus %}
          {{ bus.get('route', 'Bus') }} · leave now
        {% else %}
          Bus · leave now
        {% endif %}
      message: >-
        {% if bus %}
          {% set source = bus.get('source', 'scheduled') %}
          {% set expected = bus.get('expected') %}
          {% set destination = bus.get('destination') %}
          {% set walk = state_attr(bods_entity, 'walking_minutes') %}
          {% set timing = bus.get('timing_status') %}

          {{ bus.get('route', 'Bus') }}
          {% if destination %}to {{ destination }}{% endif %}
          {% if expected %}at {{ as_timestamp(expected) | timestamp_custom('%H:%M', true) }}{% endif %}.
          {% if walk is not none %}Allow {{ walk }} min to walk to the stop.{% endif %}
          {% if source == 'live' %}Live tracking{% else %}Timetable{% endif %}
          {% if timing == 'late' and bus.get('delay_minutes') is not none %}
            · {{ bus.get('delay_minutes') | float | round(1) }} min late
          {% elif timing == 'early' and bus.get('delay_minutes') is not none %}
            · {{ bus.get('delay_minutes') | float | abs | round(1) }} min early
          {% elif timing == 'on_time' %}
            · on time
          {% endif %}
        {% else %}
          It is time to leave for the bus.
        {% endif %}

mode: restart
```

This uses BODS's already-resolved effective walking time, so it works with static walking, HERE, another compatible provider or static fallback.

## Notify two people

A normal Home Assistant automation can simply contain two notification actions.

For example:

```yaml
alias: BODS - Leave now notify two people
description: Notify the traveller and a second person when it is time to leave.
triggers:
  - trigger: state
    entity_id: binary_sensor.YOUR_LEAVE_NOW_ENTITY
    to: "on"

conditions: []

actions:
  - action: notify.mobile_app_TRAVELLER_PHONE
    data:
      title: "Bus reminder"
      message: "It is time to leave for the bus."

  - action: notify.mobile_app_SECOND_PHONE
    data:
      title: "Bus update"
      message: "The traveller should now be leaving for the bus."

mode: restart
```

This is already possible in v0.6; no change to BODS Bus Tracker is required.

## Notify only when BODS live data are healthy

Some users may prefer not to send a leave notification during a total live-data outage.

The native **Data status** entity can be used as a condition.

However, remember that timetable fallback is an intentional feature. A `scheduled_only` state does **not** mean there are no departures; it means the current live feed is unavailable.

For many households, notifying from timetable fallback is preferable to suppressing the reminder entirely.

If you do add a condition, make that policy explicit rather than assuming timetable data are unusable.

## Trigger from Leave in instead

The **Leave now** binary sensor is the safest simple trigger because BODS has already handled the effective walking time and current departure transition.

The numeric **Leave in** sensor can be useful for earlier warnings.

For example, a template/state automation could notify at a chosen threshold before `Leave now`, but take care to avoid repeated triggers as the value updates.

For the common case, prefer **Leave now**.

## Alexa / announcement actions

The blueprint's action selector is generic, so an announcement action can be used instead of or alongside a phone notification.

Keep announcement routing and household-presence rules in Home Assistant rather than BODS Bus Tracker. The integration's responsibility is to provide the bus/walking state; Home Assistant decides who should hear or receive the message.

## What is planned for v0.7

The following are intentionally **not** documented here as working v0.6 automations:

- when a person leaves a zone, calculate the first bus they can realistically catch and the scheduled one after it;
- infer that a person boarded a particular bus;
- calculate a journey expected-arrival time from inferred boarding;
- send approaching-destination/arrival notifications from that inferred state.

Those ideas are tracked in the v0.7 roadmap:

https://github.com/IainPHay/home-assistant-bods-bus-tracker/issues/8

They will only become recommended automation recipes after the underlying state has been implemented and validated.

## Related pages

- [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time)
- [Dashboard examples](Dashboard-examples)
- [Troubleshooting live data](Troubleshooting-live-data)
