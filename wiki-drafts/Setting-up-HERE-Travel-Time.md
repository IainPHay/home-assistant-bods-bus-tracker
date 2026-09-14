# Setting up routed walking with HERE Travel Time

This guide shows how to use **HERE Travel Time** as the routed walking-time source for BODS Bus Tracker.

HERE was the routed provider used for real Home Assistant validation. The BODS integration itself remains provider-neutral: HERE creates a normal Home Assistant duration sensor and BODS simply reads that entity.

## What this gives you

With routed walking enabled, BODS Bus Tracker can use the traveller's current Home Assistant location to calculate walking time to the bus stop.

That effective walking time is used for:

- **Leave by**;
- **Leave in**;
- **Leave now**;
- v0.7 **Catchable bus** selection.

It does **not** alter BODS live matching, the selected timetable journey or the underlying ETA engine.

## 1. Create a HERE API key

HERE Travel Time requires a HERE API key.

The official Home Assistant documentation currently states that HERE's **Base Plan includes 5,000 free transactions per month**. Home Assistant notes that on-demand/custom polling can consume quota more quickly.

Create the API key using HERE's current developer/platform instructions:

- Home Assistant HERE documentation: https://www.home-assistant.io/integrations/here_travel_time/
- HERE developer platform: https://platform.here.com/

Do not put the HERE API key into BODS Bus Tracker. The key belongs only to the separate HERE Travel Time integration.

## 2. Add HERE Travel Time to Home Assistant

In Home Assistant:

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **HERE Travel Time**.
4. Enter the HERE API key.
5. Set **Travel mode** to **Pedestrian**.

For a normal "walk from the traveller to this stop" configuration, use the fastest/default route unless you have a specific reason to choose otherwise.

## 3. Configure the origin

When HERE asks for the origin, choose **Using an entity**.

Select the Home Assistant entity whose location should represent the traveller, for example:

```text
person.traveller
```

A suitable `device_tracker` can also be used if it exposes current coordinates.

### Privacy boundary

HERE owns the location lookup. BODS Bus Tracker does not need to copy the traveller's coordinates into its own state or diagnostics; it only reads the resulting duration sensor.

## 4. Configure the destination

For the destination, choose **Using a map location** and place the destination at the physical bus stop/stand.

For best results, use the actual boarding point rather than the centre of a large bus station.

You do not need to create a Home Assistant zone for the stop unless you want one for another automation.

### Important for multiple BODS stops

Create a dedicated routed duration sensor for each boarding stop you expect BODS to evaluate.

For example:

```text
HERE: traveller → The Fairway
HERE: traveller → Haymarket Stand Q
```

Each BODS stop should select the HERE Duration entity whose destination matches that stop.

Do **not** casually share one HERE duration sensor between several BODS stops. HERE may be returning a perfectly valid walking time to a different destination, and BODS cannot infer that mismatch from the numeric duration alone.

## 5. Finish HERE setup

Complete the HERE config flow.

Home Assistant creates several entities for the route. The important one for BODS is the **Duration** sensor.

A typical entity may look like:

```text
sensor.here_travel_time_duration
```

Your exact entity ID may differ.

Do **not** select Distance, Origin or Destination. BODS needs the normal duration sensor.

## 6. Check the HERE Duration sensor first

Before configuring BODS, confirm the HERE sensor is healthy.

Go to **Developer Tools → States** and find the HERE Duration entity.

You should see:

- a numeric state;
- device class: duration;
- a duration unit, commonly minutes.

Example:

```text
state: 8.9
unit_of_measurement: min
device_class: duration
friendly_name: HERE Travel Time Duration
```

BODS Bus Tracker accepts duration sensors in seconds (`s`), minutes (`min`) or hours (`h`).

## 7. Select the HERE sensor in BODS Bus Tracker

Go to:

**Settings → Devices & services → BODS Bus Tracker**

Open the bus stop and choose **Reconfigure**.

Set:

- **Static walking time to stop**: a realistic safe fallback;
- **Use routed dynamic walking time**: On;
- **Travel-time sensor**: the HERE **Duration** entity for this exact stop;
- **Maximum routed walking time**: normally leave at **120 minutes**;
- **Catchable-bus safety margin**: v0.7 only; choose the explicit extra margin you want;
- **Live update interval**: normally **30 seconds** for BODS.

Then submit the reconfiguration.

### Static walking time remains important

The static value is the fallback used when the routed source is temporarily unavailable, stale, invalid or above the configured maximum.

For normal use, set it to a realistic conservative walking time rather than zero.

A zero fallback is useful for testing, but it means walking/catchable guidance is disabled whenever the routed source cannot be trusted.

## 8. Verify BODS is using HERE

Open the BODS **Next bus** entity in **Developer Tools → States**.

When HERE is valid, attributes should resemble:

```yaml
walking_minutes: 9
walking_mode: dynamic
walking_time_entity: sensor.here_travel_time_duration
walking_dynamic_minutes: 8.9
walking_max_dynamic_minutes: 120
walking_fallback: false
walking_source_status: ok
leave_by: "..."
leave_in_minutes: 12
leave_now: false
```

BODS rounds a valid fractional routed duration **up** to a whole minute for passenger guidance.

## 9. Verify Catchable bus in v0.7

Open the stop's **Catchable bus** entity.

A trusted state resembles:

```yaml
status: ok
walking_minutes: 9
margin_minutes: 3
required_lead_minutes: 12
departure:
  route: X18
  expected: "..."
following_departure:
  route: X18
  expected: "..."
```

The safety margin is added by BODS after the effective walking time has been resolved.

Catchability does not cause additional HERE API requests.

## 10. Understand fallback behaviour

Temporary routing problems should not break bus tracking.

### HERE unavailable

Expected BODS behaviour:

```yaml
walking_mode: static_fallback
walking_fallback: true
walking_source_status: unavailable
```

BODS continues using the static walking time.

### HERE route exceeds the configured maximum

The routed result is rejected and static fallback is used.

This protects against excessive routes and some configuration/location failures, but it is **not** a substitute for configuring the correct destination.

A route to the wrong stop can still be numerically plausible and pass the maximum check.

### HERE recovers

BODS automatically switches back to dynamic walking. Reconfiguration is not required.

### Selected sensor is deleted or renamed

BODS raises a Home Assistant Repair because the configured entity genuinely no longer exists.

The Repair self-clears when the configuration is corrected or routed walking is disabled.

## 11. API quota and polling

The **BODS live update interval** and the **HERE polling interval** are separate.

A 30-second BODS interval does **not** cause HERE to be queried every 30 seconds. BODS only reads the latest state held by Home Assistant.

The current Home Assistant HERE integration normally refreshes the route on its own cadence. HERE owns those API calls and the associated quota; BODS does not add HERE requests.

Home Assistant also supports on-demand updates with:

```yaml
action: homeassistant.update_entity
target:
  entity_id: sensor.here_travel_time_duration
```

Use on-demand updating carefully because provider refreshes can consume quota.

## 12. Zone-exit notification

Once Catchable bus reports `status: ok`, the v0.7 beta zone-exit blueprint can notify a traveller when they leave a chosen origin zone.

The blueprint consumes the Catchable bus state; it does not calculate another walking route itself.

See [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications).

## 13. Privacy

BODS diagnostics may contain the configured duration entity ID, for example:

```text
sensor.here_travel_time_duration
```

They should not contain:

- the HERE API key;
- traveller person/device coordinates;
- HERE account credentials.

Always review diagnostics before posting them publicly.

## Troubleshooting

### BODS shows `walking_source_status: unavailable`

Check the HERE Duration entity directly in **Developer Tools → States**.

If HERE itself is unavailable, BODS is behaving correctly by using static fallback.

### BODS shows `walking_source_status: invalid`

Check:

- the selected entity is the **Duration** sensor;
- the state is numeric;
- the unit is `s`, `min` or `h`;
- the duration is below **Maximum routed walking time**;
- the HERE destination is the same boarding stop BODS is evaluating.

### Walking time does not change as the person moves

First check that the Home Assistant `person` / `device_tracker` coordinates are changing.

Then check when HERE last updated. BODS does not force HERE to recalculate on every bus poll.

### Walking time is unexpectedly huge

Check the destination first.

A large duration can be completely legitimate if the traveller is far from the stop, but a destination accidentally pointing at another monitored stop can also produce a valid-but-wrong value.

The maximum routed walking setting can trigger static fallback for excessive values, but correct stop-specific routing remains the preferred solution.

## Related pages

- [Routed walking providers](Routed-walking-providers)
- [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications)
- [Automation recipes](Automation-recipes)
- [Troubleshooting live data](Troubleshooting-live-data)

---