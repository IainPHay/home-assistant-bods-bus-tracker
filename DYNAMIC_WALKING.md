# Routed dynamic walking time

BODS Bus Tracker 0.6 adds an optional provider-neutral routed walking-time source for each monitored stop.

The integration does **not** call HERE or Google itself. Instead, configure a Home Assistant travel-time sensor separately and select that sensor when reconfiguring the bus stop. This keeps routing credentials and provider billing outside BODS Bus Tracker and means other compatible duration sensors can be used later.

## How it works

Each stop retains the existing **Static walking time to stop** setting. When **Use routed dynamic walking time** is enabled, BODS Bus Tracker reads the selected **Travel-time sensor**.

A valid routed value overrides the static time. If the dynamic sensor is missing, `unknown`, `unavailable`, stale, non-numeric, negative, has an unsupported unit, or exceeds 120 minutes, the integration automatically falls back to the configured static walking time. If that static fallback is `0`, Leave by / Leave in / Leave now guidance is disabled until the dynamic sensor becomes valid again.

Dynamic walking affects only walking guidance. It never changes BODS/GTFS matching, the predicted bus time, the selected next bus, or terminus arrival/departure logic.

## Supported sensor values

The selected sensor must expose a finite non-negative duration using one of these units:

- seconds (`s`);
- minutes (`min`);
- hours (`h`).

The routed value is normalised to minutes and rounded **up** to the next whole minute for safe leave guidance.

The source is considered stale if Home Assistant has not reported it for 30 minutes. This is deliberately much longer than the normal HERE/Google polling cadence so an unchanged but regularly reported route remains valid.

## HERE Travel Time example

1. In Home Assistant, add **HERE Travel Time** under **Settings → Devices & services** and configure its HERE API key.
2. Configure the route's **Origin** as the `person` or `device_tracker` entity that represents the traveller.
3. Configure the **Destination** as the bus-stop coordinates (or another Home Assistant entity representing those coordinates).
4. Select **walking** as the HERE transport mode.
5. Confirm the HERE sensor reports a duration in Home Assistant.
6. Reconfigure the BODS Bus Tracker stop:
   - leave **Static walking time to stop** set to the fallback you want;
   - enable **Use routed dynamic walking time**;
   - choose the HERE duration sensor as **Travel-time sensor**.

HERE Travel Time can resolve dynamic `person` and `device_tracker` origins. Provider polling remains owned by HERE Travel Time; BODS Bus Tracker only reads its current sensor state.

## Google Maps Travel Time example

1. In Home Assistant, add **Google Maps Travel Time** and configure the Google Routes API credentials/billing required by that integration.
2. Configure the **Origin** as the traveller's `person` or `device_tracker` entity.
3. Configure the **Destination** as the bus stop.
4. Configure the route for **walking** travel where supported by the Home Assistant Google Travel Time setup.
5. Confirm the resulting sensor exposes travel time as a duration.
6. Reconfigure the BODS stop and select that sensor as **Travel-time sensor**.

Google Maps Travel Time also supports dynamic Home Assistant entity locations. BODS Bus Tracker does not store the Google API key and does not make Google API calls.

## Polling and API usage

BODS Bus Tracker deliberately does **not** force-update the routing sensor on its own 30-second live-bus polling cycle. HERE/Google retain responsibility for their own polling and API quotas.

If more frequent walking-route updates are needed, configure that on the travel-time integration itself, for example with Home Assistant's `homeassistant.update_entity` action after disabling the provider's normal polling. Be mindful of provider request limits and billing.

## Runtime attributes

The native **Next bus** entity exposes troubleshooting attributes while walking guidance is active:

```yaml
walking_mode: dynamic
walking_minutes: 8
walking_time_entity: sensor.walk_to_the_fairway
walking_dynamic_minutes: 7.4
walking_fallback: false
walking_source_status: ok
```

Possible `walking_mode` values are:

- `static` — existing fixed walking time;
- `dynamic` — valid routed duration is being used;
- `static_fallback` — dynamic source failed and the fixed fallback is active;
- `disabled` — no usable walking time is currently available.

Possible source statuses include `ok`, `disabled`, `not_configured`, `missing`, `unknown`, `unavailable`, `stale`, and `invalid`.

No person/device coordinates are copied into BODS Bus Tracker diagnostics or walking attributes.

## Terminus behaviour

For **Arrivals and departures**, dynamic walking remains tied to the next boardable departure, exactly like static walking time. **Arrivals** mode continues to disable leave guidance because there is no boardable departure selected.
