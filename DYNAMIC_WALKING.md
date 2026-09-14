# Routed dynamic walking time

BODS Bus Tracker v0.6 introduced an optional provider-neutral routed walking-time source for each monitored stop. v0.7 keeps that provider boundary unchanged and also uses the resolved walking time as an input to native **Catchable bus** guidance.

The integration does **not** call HERE, Google, or another routing provider itself. Instead, configure a Home Assistant duration/travel-time sensor separately and select that entity when adding or reconfiguring the bus stop. BODS Bus Tracker only reads the selected entity's current duration value.

This keeps routing credentials, location handling and provider billing outside BODS Bus Tracker. The runtime does not care which integration created the sensor as long as it follows the duration contract described below.

## How it works

Each stop retains the existing **Static walking time to stop** setting. When **Use routed dynamic walking time** is enabled, BODS Bus Tracker reads the selected **Travel-time sensor**.

A valid routed value overrides the static time. If the dynamic sensor is missing, `unknown`, `unavailable`, stale, non-numeric, negative, has an unsupported unit, or exceeds the configured **Maximum routed walking time**, the integration automatically falls back to the configured static walking time. The maximum defaults to **120 minutes** and can be changed independently for each stop. If the static fallback is `0`, Leave by / Leave in / Leave now guidance is disabled until the dynamic sensor becomes valid again.

Dynamic walking remains downstream of BODS/GTFS matching. It never changes live matching, the predicted bus time, the selected next bus, or terminus arrival/departure logic. In v0.7 the already-resolved effective walking time can also feed Catchable bus state; catchability still does not alter ETA/matching.

## Maximum routed walking time

Each stop has a **Maximum routed walking time** safety limit. The default is **120 minutes** and it can be configured from 1 to 1440 minutes.

The limit is deliberately separate from the static fallback:

- the **Static walking time to stop** is the value used when routed walking cannot be trusted;
- the **Maximum routed walking time** determines whether a valid provider duration is plausible enough to use.

For example, a stop configured with a 480-minute maximum can accept a HERE result of 407 minutes, while another stop can retain the conservative 120-minute default.

## Stop-specific routing for moving travellers

For a moving `person` or `device_tracker`, the selected duration entity should represent:

```text
current traveller location → this exact monitored boarding stop
```

If several BODS stops are configured, the safest architecture is normally **one routed duration sensor per stop**, each with the appropriate fixed destination.

A single shared routing sensor can report a perfectly valid duration to the wrong stop. BODS only sees the duration value and cannot infer the provider's destination from that number.

The **Maximum routed walking time** can reject an extreme value and fall back to static walking, but it is not destination validation. A plausible-but-wrong duration could still be accepted.

This matters even more in v0.7 because the effective walking time contributes directly to Catchable bus selection.

## Provider-neutral sensor contract

The selected Home Assistant entity is the only interface BODS Bus Tracker needs from a routing provider.

The sensor must:

- have a numeric, finite, non-negative state;
- represent a **duration**, not a distance or arrival timestamp;
- use one of these units: seconds (`s`), minutes (`min`) or hours (`h`);
- be updated by its own integration often enough for the user's walking guidance needs.

The routed value is normalised to minutes and rounded **up** to the next whole minute for safe leave guidance.

BODS Bus Tracker does not require a specific entity ID, integration platform, provider account, person entity or device tracker. Those are concerns of the routing integration that creates the duration sensor. In the BODS stop configuration you simply select the resulting duration entity.

The source is considered stale if Home Assistant has not reported it for 30 minutes. This is deliberately much longer than typical travel-time polling so an unchanged but regularly reported route remains valid.

### Provider compatibility

| Provider/source | Project status | What BODS Bus Tracker requires |
| --- | --- | --- |
| **HERE Travel Time** | **Live-validated** | Select the HERE duration sensor for the same stop. A dynamic Home Assistant `person` origin and pedestrian route have been exercised end-to-end. |
| **Google Maps Travel Time** | Compatible in principle; not the primary project validation path | The Home Assistant integration must expose a walking/travel duration sensor using a supported unit. |
| **Another Home Assistant duration sensor** | Provider-neutral compatibility | It can be used if it follows the numeric duration/unit/staleness rules above. |

v0.7 broadens the guidance around provider portability without changing this provider-neutral runtime contract. Alternative providers should remain separate Home Assistant routing layers rather than adding routing credentials or provider-specific API calls to BODS.

## HERE Travel Time example — live-validated in v0.6

The v0.6 release was exercised with HERE Travel Time using a Home Assistant `person` as the dynamic origin.

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

## Google Maps Travel Time compatibility example

Google Maps Travel Time was **not** part of the project's live v0.6 validation, so treat this as compatibility guidance rather than a tested provider recipe.

1. Configure the Home Assistant Google travel-time integration according to its current requirements.
2. Configure an origin/destination and walking mode if that integration/setup supports the combination you need.
3. Confirm the resulting Home Assistant entity reports a numeric duration in `s`, `min` or `h`.
4. Reconfigure the BODS stop and select that duration entity as **Travel-time sensor**.

BODS Bus Tracker does not store the Google credential, inspect the provider configuration, or make Google API calls. If the selected entity obeys the provider-neutral sensor contract above, BODS can consume it.

## Polling and API usage

BODS Bus Tracker deliberately does **not** force-update the routing sensor on its own 30-second live-bus polling cycle. The routing integration retains responsibility for its own polling, request quotas and billing.

If more frequent walking-route updates are needed, configure that on the provider/integration side. Be mindful of provider request limits and billing; a BODS polling interval of 30 seconds does not mean the routing provider should also be called every 30 seconds.

## Runtime attributes

The native **Next bus** entity exposes troubleshooting attributes while walking guidance is active:

```yaml
walking_mode: dynamic
walking_minutes: 8
walking_time_entity: sensor.walk_to_the_fairway
walking_dynamic_minutes: 7.4
walking_max_dynamic_minutes: 120
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

## Repairs and missing source entities

Temporary routing-provider problems are treated differently from a deleted/renamed source entity.

- `unknown`, `unavailable`, stale or invalid provider states use the configured static fallback and do **not** create a Repair.
- If the configured travel-time entity itself no longer exists, BODS Bus Tracker uses the static fallback and raises the translated Home Assistant Repair **Dynamic walking-time sensor is missing**.
- The Repair self-clears when the source is corrected or routed dynamic walking is disabled.

This behaviour was validated in real Home Assistant during the beta.5 test cycle.

## v0.6 validation status

Stable v0.6.0 completed both automated and real Home Assistant validation. The routed-walking checks included:

- valid HERE duration accepted in dynamic mode;
- upward rounding to a whole walking minute;
- configurable maximum duration, including acceptance of a real ~407-minute route when the ceiling was temporarily raised to 500 minutes;
- temporary provider `unavailable` fallback to static walking without a false Repair;
- automatic recovery back to dynamic mode without reconfiguring BODS;
- a real location-driven HERE result near Haymarket using the configured Home Assistant person origin;
- missing-entity Repair creation and self-clear behaviour.

The durable validation record is maintained in [`V0.6_VALIDATION.md`](V0.6_VALIDATION.md).
