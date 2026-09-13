# Setting up routed walking with HERE Travel Time

This guide shows how to use **HERE Travel Time** as the routed walking-time source for BODS Bus Tracker.

HERE was the routed provider used for the real v0.6 Home Assistant validation. The BODS integration itself remains provider-neutral: HERE creates a normal Home Assistant duration sensor and BODS simply reads that entity.

## What this gives you

With routed walking enabled, BODS Bus Tracker can use the traveller's current Home Assistant location to calculate walking time to the bus stop.

That effective walking time is then used for:

- **Leave by**;
- **Leave in**;
- **Leave now**.

It does **not** alter BODS live matching, the selected departure, or the bus ETA.

## 1. Create a HERE API key

HERE Travel Time requires a HERE API key.

The official Home Assistant documentation currently states that HERE's **Base Plan includes 5,000 free transactions per month**.

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

Select the Home Assistant entity whose location should represent the traveller.

A typical choice is:

```text
person.traveller
```

A suitable `device_tracker` can also be used if it exposes current coordinates.

The v0.6 live validation used a Home Assistant `person` entity as the dynamic origin.

### Important

HERE owns the location lookup. BODS Bus Tracker does not read or store the traveller's coordinates; it only reads the resulting duration sensor.

## 4. Configure the destination

For the destination, choose **Using a map location** and place the destination at the bus stop.

For best results, use the actual boarding stop/stand coordinates rather than the centre of a large bus station.

For example, the v0.6 Haymarket validation used the coordinates of **Haymarket Bus Station Stand Q**, not simply "Newcastle city centre".

You do not need to create a Home Assistant zone for the stop unless you want one for another automation.

## 5. Finish HERE setup

Complete the HERE config flow.

Home Assistant creates several entities for the route. The important one for BODS is the **Duration** sensor.

A typical entity may look like:

```text
sensor.here_travel_time_duration
```

Your exact entity ID may differ.

Do **not** select:

- Distance;
- Origin;
- Destination.

For pedestrian routing, the normal **Duration** sensor is the value BODS Bus Tracker needs.

## 6. Check the HERE Duration sensor first

Before configuring BODS, confirm the HERE sensor is healthy.

Go to **Settings → Tools → States** and find the HERE Duration entity.

You should see:

- a numeric state;
- device class: duration;
- a duration unit, commonly minutes in the UI.

Example:

```text
state: 8.9
unit_of_measurement: min
device_class: duration
friendly_name: HERE Travel Time Duration
```

BODS Bus Tracker accepts duration sensors in:

- seconds (`s`);
- minutes (`min`);
- hours (`h`).

## 7. Select the HERE sensor in BODS Bus Tracker

Go to:

**Settings → Devices & services → BODS Bus Tracker**

Open the bus stop and choose **Reconfigure**.

Set:

- **Static walking time to stop**: your safe fallback value;
- **Use routed dynamic walking time**: On;
- **Travel-time sensor**: the HERE **Duration** entity;
- **Maximum routed walking time**: normally leave at **120 minutes**;
- **Live update interval**: normally **30 seconds** for BODS.

Then submit the reconfiguration.

### Static walking time is still important

The static value is the fallback used when the routed source is temporarily unavailable, stale, invalid or above the configured maximum.

For normal use, set it to a realistic conservative walking time rather than zero.

A zero fallback is useful for testing, but it means leave guidance is disabled whenever the routed source cannot be trusted.

## 8. Verify BODS is using HERE

Open the BODS **Next bus** entity in **Settings → Tools → States**.

When HERE is valid, the BODS attributes should include values similar to:

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

BODS rounds a valid fractional routed duration **up** to a whole minute for leave guidance.

For example:

```text
HERE duration = 8.4 min
effective walking_minutes = 9
```

## 9. Understand fallback behaviour

Temporary routing problems should not break bus tracking.

Examples:

### HERE unavailable

Expected BODS behaviour:

```yaml
walking_mode: static_fallback
walking_fallback: true
walking_source_status: unavailable
```

BODS continues using the static walking time.

### HERE route is longer than the configured maximum

The routed result is rejected and the static fallback is used.

This protects against obviously inappropriate routes, stale location data or accidental configuration mistakes.

### HERE recovers

BODS automatically switches back to dynamic walking. Reconfiguration is not required.

### Selected sensor is deleted or renamed

BODS raises a Home Assistant Repair because the configured entity genuinely no longer exists.

The Repair self-clears when the configuration is corrected or routed walking is disabled.

## 10. API quota and polling

The **BODS live update interval** and the **HERE polling interval** are separate things.

A 30-second BODS interval does **not** cause HERE to be queried every 30 seconds. BODS only reads the latest state already held by Home Assistant.

The HERE integration owns its own API calls and quota.

Home Assistant also supports on-demand updates with:

```yaml
action: homeassistant.update_entity
target:
  entity_id: sensor.here_travel_time_duration
```

Use on-demand updating carefully. Every provider refresh can consume API quota.

The Home Assistant HERE documentation currently states that the Base Plan provides **5,000 free transactions per month**, so frequent unconditional polling is not a good default.

A better future pattern is to refresh only when it is useful, for example around an expected journey or after meaningful movement.

## 11. Privacy

BODS Bus Tracker deliberately keeps the routing-provider boundary separate.

BODS diagnostics should contain the selected entity ID, for example:

```text
sensor.here_travel_time_duration
```

They should not contain:

- the HERE API key;
- the traveller's person/device coordinates;
- HERE account credentials.

Always review diagnostics yourself before posting them publicly.

## Troubleshooting

### BODS shows `walking_source_status: unavailable`

Check the HERE Duration entity directly in **Settings → Tools → States**.

If HERE itself is unavailable, BODS is behaving correctly by using the static fallback.

### BODS shows `walking_source_status: invalid`

Check:

- the selected entity is the **Duration** sensor;
- the state is numeric;
- the unit is `s`, `min` or `h`;
- the duration is below **Maximum routed walking time**.

### The walking time does not change as the person moves

First check that the Home Assistant `person` / `device_tracker` coordinates are actually changing.

Then check when HERE last updated. BODS does not force HERE to recalculate on every bus poll.

### The walking time is unexpectedly huge

This can be completely valid if the person is geographically far from the stop.

During v0.6 testing, the same HERE route was roughly **407 minutes** while the tracked person was far from Newcastle, then about **22 minutes** when near Haymarket.

The maximum routed walking-time setting exists specifically so a very large value can fall back safely during ordinary use.

## Related pages

- [Routed walking providers](Routed-walking-providers)
- [Automation recipes](Automation-recipes)
- [Troubleshooting live data](Troubleshooting-live-data)
