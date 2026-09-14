# Catchable bus and zone-exit notifications

This page describes the v0.7 beta **Catchable bus** state and the reusable **zone-exit catchable-bus notification** blueprint.

The feature is deliberately downstream of the existing ETA/matching engine. It does not change live-to-GTFS matching, selected Next bus state or timetable ordering.

## Catchability rule

For departure and combined stop views:

```text
required lead time =
    effective walking minutes
  + configured safety margin

first catchable departure =
    first ordered departure where
    expected departure >= now + required lead time
```

The passenger-facing `expected` time is used when available, falling back to `scheduled`.

That means a genuine live delay can make a bus catchable without changing the underlying matching policy.

## Catchable-bus safety margin

Each monitored stop has an explicit **Catchable-bus safety margin**.

- default: **0 minutes**
- supported range: **0–30 minutes**

A zero margin means "conceivably catchable": if the effective walking time fits before departure, the journey can be selected.

If you want a more conservative policy, configure the margin on the stop itself.

Do not add a second hidden margin in the automation.

## Catchable bus entity

When the state is trusted, the sensor state is the selected route and its attributes include:

```yaml
status: ok
walking_minutes: 34
margin_minutes: 0
required_lead_minutes: 34
departure:
  route: X15
  destination: Bus Station
  scheduled: "..."
  expected: "..."
  source: scheduled
  realtime: false
  timing_status: timetable
following_departure:
  route: X16
  destination: Bus Station
  scheduled: "..."
  expected: "..."
```

Possible non-`ok` statuses include:

- `walking_disabled`
- `no_departures`
- `none_in_window`
- `arrivals_only`

The Catchable bus entity is unavailable unless the status is `ok` and a selected departure exists.

## Privacy boundary

Catchable/following-departure summaries are intentionally restricted to automation-friendly passenger information.

They exclude:

- live vehicle latitude/longitude;
- trip IDs;
- person/device coordinates;
- routing-provider credentials.

The full internal departure sequence used for the catchability calculation is transient private scratch state and is not intended for entities or diagnostics.

## Zone-exit blueprint

Development source:

[BODS Bus Tracker - Zone exit catchable bus notification](https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/feature/v0.7/blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml)

The blueprint triggers when a selected Home Assistant `person` leaves a selected `zone`.

Inputs:

- traveller;
- origin zone;
- BODS **Catchable bus** sensor for the intended boarding stop;
- notification title;
- primary notification/announcement action;
- optional second action.

The blueprint only runs its notification actions if Catchable bus reports `status: ok`.

It does **not** recalculate catchability in YAML.

## Import the blueprint

1. Open **Settings → Automations & scenes → Blueprints**.
2. Select **Import Blueprint**.
3. Paste:

   ```text
   https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/feature/v0.7/blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml
   ```

4. Preview and import.
5. Create an automation.
6. Choose the traveller.
7. Choose the origin zone.
8. Choose the appropriate BODS **Catchable bus** sensor.
9. Configure the primary notification action.
10. Optionally configure a second action.
11. Save.

## Companion App notification

A typical action is:

```yaml
action: notify.mobile_app_YOUR_PHONE
data:
  title: "{{ bods_title }}"
  message: "{{ bods_message }}"
```

In the visual action editor, `{{ bods_message }}` belongs in **message**, not in the generic **data** mapping field.

## Example notification

For timetable-only state:

```text
Catchable: X15 to Bus Station — expected 14:38; scheduled 14:38 · 36 min away · timetable. Walking: 34 min (34 min required lead). Following: X16 to Bus Station — expected 14:53; scheduled 14:53 · timetable.
```

For a live journey, the message can additionally report timing status and effective delay.

## Routed walking requirement

The blueprint is only as meaningful as the walking duration supplied to the selected stop.

For a moving traveller, use a routed-walking sensor whose:

- origin follows that traveller;
- destination is the same physical boarding stop represented by the BODS Catchable bus entity.

For multiple monitored boarding stops, the safest pattern is normally **one routed duration sensor per stop**.

Do not reuse one duration sensor across several BODS stops unless its destination is guaranteed to match the stop currently consuming it.

A duration can be perfectly valid for the routing provider and still be the wrong input for BODS if it points to a different stop.

## Refreshing an imported beta blueprint

During beta testing the source may change.

To refresh:

1. open **Settings → Automations & scenes → Blueprints**;
2. use the blueprint's menu and choose **Re-import** / **Update blueprint** where available;
3. otherwise import the same GitHub source URL again.

Your existing automation should keep its selected entities/actions because it continues to reference the same blueprint path.

## Validation status

Catchable bus has passed real Home Assistant validation for:

- a genuinely catchable departure;
- explicit-margin rejection;
- routed-walking fallback to static time;
- walking-disabled suppression;
- arrivals-only suppression;
- privacy-safe diagnostics.

The zone-exit blueprint has passed controlled Home Assistant execution:

- trusted Catchable bus state was consumed;
- message variables rendered correctly;
- timetable fallback rendered correctly;
- Companion App notify service invocation completed normally;
- formatting was corrected and re-tested.

A manual **Run actions** test bypasses the zone trigger. The remaining beta gate is therefore a genuine person leaving the configured origin zone and confirmation of receipt on the target device.

## Related pages

- [Automation recipes](Automation-recipes)
- [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time)
- [Routed walking providers](Routed-walking-providers)
- [Troubleshooting live data](Troubleshooting-live-data)

---