# Automation recipes

BODS Bus Tracker exposes automation-friendly entities and attributes so Home Assistant can act on trusted bus state without putting notification logic inside the integration.

There are now two distinct automation patterns:

1. stable v0.6 **Leave now** guidance;
2. v0.7 beta **Catchable bus / zone-exit** guidance.

The important design rule is the same for both: **consume BODS's derived state rather than recreating ETA, walking or catchability logic in YAML.**

## Leave-now notification blueprint — stable v0.6

The repository includes a generic blueprint:

[BODS Bus Tracker - Leave now notification](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/blueprints/automation/bods_bus_tracker_leave_now.yaml)

It triggers when a stop's native **Leave now** binary sensor changes to `on`.

The blueprint does not hard-code a notification provider. Its action can be a Companion App notification, announcement, script, multiple actions, or another normal Home Assistant action sequence.

### Import the Leave now blueprint

1. Go to **Settings → Automations & scenes → Blueprints**.
2. Select **Import Blueprint**.
3. Use:

   ```text
   https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/blueprints/automation/bods_bus_tracker_leave_now.yaml
   ```

4. Preview and import it.
5. Find **BODS Bus Tracker - Leave now notification** and select **Create automation**.
6. Choose the stop's **Leave now** binary sensor.
7. Configure the notification/announcement action.
8. Save the automation.

## Zone-exit catchable-bus blueprint — v0.7 beta

The v0.7 beta blueprint answers a different question:

> When this person leaves this zone, what is the first bus they can realistically catch from the configured stop, and what comes after it?

Development source:

[BODS Bus Tracker - Zone exit catchable bus notification](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/feature/v0.7/blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml)

It uses the native **Catchable bus** sensor. It does **not** inspect the raw departure list or perform its own threshold calculation.

The Catchable bus sensor has already applied:

- effective routed or static walking time;
- static fallback policy;
- the configured safety margin;
- passenger-facing expected departure time, with timetable fallback;
- the complete ordered departure set.

The blueprint only proceeds while the Catchable bus sensor reports `status: ok`.

See the dedicated [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications) page for full setup.

### Import or refresh the beta blueprint

For first import:

1. Go to **Settings → Automations & scenes → Blueprints**.
2. Select **Import Blueprint**.
3. Paste the GitHub URL above.
4. Preview and import.
5. Create an automation from the blueprint.

If the beta blueprint changes while you are testing it:

1. Return to **Settings → Automations & scenes → Blueprints**.
2. Open the menu for **BODS Bus Tracker - Zone exit catchable bus notification**.
3. Choose **Re-import** / **Update blueprint** where offered.
4. If that option is not shown, import the same source URL again; Home Assistant should recognise the existing source.

Existing automations continue using the same blueprint path and retain their selected inputs.

## Companion App notification action

For the zone-exit blueprint the ready-to-send variables are:

- `{{ bods_title }}`
- `{{ bods_message }}`

For a phone-specific Companion App action:

```yaml
action: notify.mobile_app_YOUR_PHONE
data:
  title: "{{ bods_title }}"
  message: "{{ bods_message }}"
```

### UI note: use Message, not Data

When configuring the action in Home Assistant's visual editor:

- put `{{ bods_message }}` in the **message** field;
- put `{{ bods_title }}` in the **title** field;
- leave **target** empty unless your notify action specifically needs it;
- do not put `{{ bods_message }}` into the generic **data** mapping field.

The generic data field expects a mapping, not the notification message string.

## What the zone-exit message contains

A typical timetable-fallback message is:

```text
Catchable: X15 to Bus Station — expected 14:38; scheduled 14:38 · 36 min away · timetable. Walking: 34 min (34 min required lead). Following: X16 to Bus Station — expected 14:53; scheduled 14:53 · timetable.
```

When live matching is available, the same message can include live timing and delay information.

## Optional second recipient

The zone-exit blueprint provides:

- one required primary action;
- one optional second action.

The second action can notify another phone, announce in the house, call a script, or run another Home Assistant action sequence.

Keep household-specific routing/privacy rules in Home Assistant. BODS's job is to provide trusted transport state.

## Safety margin

Do **not** add another margin inside the automation.

Set **Catchable-bus safety margin** on the BODS stop configuration. The integration then exposes:

```yaml
walking_minutes: 5
margin_minutes: 3
required_lead_minutes: 8
```

The blueprint consumes those values directly.

## Timetable fallback is intentional

A catchable departure can be based on live timing or the published timetable.

A temporary lack of a live vehicle match does not automatically make the departure unusable. The notification explicitly indicates whether its selected departure is live or timetable-only.

## Current beta validation state

The v0.7 Catchable bus state has passed real Home Assistant validation.

The zone-exit blueprint has also passed a controlled **Run actions** test proving:

- `status: ok` is consumed correctly;
- the catchable and following departures are read correctly;
- walking/margin/required-lead values are preserved;
- the message renders cleanly;
- the configured Companion App notify service is called successfully.

A manual **Run actions** execution has no real zone trigger, so the remaining live gate is a genuine person leaving the configured origin zone and confirmation that the notification appears on the phone.

## Boarding inference is still future work

The following remain intentionally experimental/planned and are **not** yet trusted automations:

- infer that a person boarded a particular bus;
- calculate a journey ETA from inferred boarding;
- send approaching-destination/arrival notifications from that inferred state.

Those are tracked in the v0.7 roadmap:

https://github.com/IainPHay/home-assistant-bods-bus-tracker/issues/8

## Related pages

- [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications)
- [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time)
- [Routed walking providers](Routed-walking-providers)
- [Dashboard examples](Dashboard-examples)
- [Troubleshooting live data](Troubleshooting-live-data)

---