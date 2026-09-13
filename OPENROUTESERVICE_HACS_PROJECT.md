# OpenRouteService Home Assistant HACS integration — project bootstrap

This branch is a temporary project bootstrap for a **standalone Home Assistant custom integration** for openrouteservice.

It is intentionally separate from BODS Bus Tracker runtime development. The target architecture is a new repository in its own right, suitable for HACS installation and useful beyond buses.

## Proposed repository and domain

Recommended repository name:

```text
home-assistant-openrouteservice-travel-time
```

Recommended Home Assistant domain:

```text
openrouteservice_travel_time
```

Do **not** reuse the legacy `open_route_service` domain. The archived HACS integration by Kevin Eifinger used that domain, and Home Assistant recommends unique custom-integration domains rather than overriding another integration.

## Why make it standalone?

The routing problem is generic Home Assistant functionality:

```text
dynamic origin -> route provider -> duration/distance sensors -> any downstream consumer
```

BODS Bus Tracker is just one consumer.

A standalone integration would also support:

- commute times;
- walking time to stations/stops;
- cycling routes;
- travel-time automations;
- dashboards;
- any other Home Assistant integration/template that consumes a duration sensor.

This preserves the v0.6/v0.7 BODS rule that routing is downstream and provider-neutral.

## Relationship with BODS Bus Tracker

BODS should continue to read a normal Home Assistant duration entity.

The OpenRouteService integration should own:

- API credentials;
- routing API calls;
- origin/destination resolution;
- route profile;
- polling;
- rate-limit/backoff behaviour.

BODS should **not** import or depend on its Python code.

For BODS, the contract remains simply:

- finite non-negative numeric duration;
- unit `s`, `min` or `h`;
- normal Home Assistant availability semantics.

## Existing archived integration

The previous project:

```text
https://github.com/eifinger/open_route_service
```

is archived and explicitly states that it is no longer maintained.

It used:

- YAML-only configuration;
- domain `open_route_service`;
- Python package `openrouteservice==2.3.3`;
- dynamic entity locations;
- travel-time sensors;
- 5-minute polling.

Its licence is **MIT**, so code can legally be reused or adapted if the copyright notice and licence terms are preserved.

However, the new project should be a modern Home Assistant implementation rather than a drop-in resurrection:

- UI config flow;
- translations;
- config entries/options;
- modern entity/device classes;
- Home Assistant-native tests;
- HACS/Hassfest validation;
- diagnostics;
- reauth;
- clean unload;
- current openrouteservice API host.

## Current openrouteservice API

The current hosted API uses:

```text
https://api.heigit.org/openrouteservice/v2/
```

The old host:

```text
https://api.openrouteservice.org/
```

was deprecated in April 2026 and is scheduled to be shut down on **2026-09-28**.

For directions, the API supports:

```text
/openrouteservice/v2/directions/{profile}
```

Authentication can use the `Authorization` header.

The integration should use the new `api.heigit.org` host from day one.

## Why openrouteservice is attractive

The hosted service supports:

- walking / foot profiles;
- cycling;
- driving;
- wheelchair;
- global routing based on OpenStreetMap;
- public hosted API;
- a self-hostable backend.

The openrouteservice site currently advertises **over 7,000 free requests per day**, which is materially more useful for dynamic Home Assistant route sensors than a 5,000-request/month allowance.

## Proposed v0.1 feature set

Keep the first release small and reliable.

### Account/configuration

Use a UI config flow.

Required:

- openrouteservice API key.

Optional later:

- custom/self-hosted base URL.

### Route configuration

A route should support:

- friendly name;
- origin from:
  - Home Assistant entity with coordinates, especially `person` and `device_tracker`;
  - fixed map/GPS coordinates;
- destination from:
  - Home Assistant entity with coordinates;
  - fixed map/GPS coordinates;
- profile:
  - `foot-walking`;
  - `cycling-regular`;
  - `driving-car`;
- configurable polling interval with a conservative default of 5 minutes.

The design should not be BODS-specific.

### Entities

At minimum expose:

- **Duration**
  - device class: duration;
  - native unit: seconds;
  - suggested display unit: minutes;
- **Distance**
  - device class: distance;
  - native unit: metres or kilometres.

Potential later diagnostics:

- last successful update;
- API/status diagnostic entity;
- resolved origin;
- resolved destination.

Avoid copying precise moving-person coordinates into Recorder attributes unnecessarily.

## Preferred Home Assistant structure

A clean first implementation could use one config entry per route.

Pros:

- simplest config/reconfigure flow;
- each route has one logical service device;
- easy to delete/reconfigure independently.

Alternative later:

- one account/key parent with route subentries.

The parent/subentry pattern is attractive if users create many routes, but it adds complexity. Do not adopt it until the simple model proves insufficient.

## HTTP/API implementation

Prefer direct asynchronous calls through Home Assistant's shared `aiohttp` session rather than depending on the legacy Python SDK unless current SDK maintenance clearly justifies it.

Reasons:

- very small API surface is required;
- guarantees use of the new `api.heigit.org` endpoint;
- removes an unnecessary package dependency;
- straightforward timeout, 401/403, 429 and server-error handling;
- easier Home Assistant test mocking.

A directions request only needs origin, destination and profile for the initial use case.

## Availability/error policy

Suggested behaviour:

- 401/403 explicit bad credential -> reauthentication;
- 429 -> unavailable/update failure with rate-limit backoff, not credential invalidation;
- timeout/connection/server error -> retain last good sensor state through coordinator semantics where appropriate;
- invalid/missing dynamic origin coordinates -> entity unavailable with a clear translated error;
- route-not-found -> unavailable, not an integration crash.

Do not silently substitute straight-line distance or guessed duration.

## Polling

Default target: **5 minutes**.

Support `homeassistant.update_entity` naturally through the coordinator/entity model.

Do not force updates merely because BODS polls more frequently.

Later optimisation could skip calls while a dynamic origin has not materially moved, but only if it can be implemented transparently and safely.

## Home Assistant quality target

Build to the same standards established in BODS Bus Tracker:

- config flow only;
- translations;
- reconfigure/reauth where appropriate;
- strict typing;
- HACS validation;
- Hassfest;
- Home Assistant-native pytest suite;
- >=95% coverage target;
- clean unload;
- diagnostics with API key redaction;
- no secrets in entity attributes;
- clear documentation.

Describe it as quality-scale aligned / Platinum-equivalent only if the applicable requirements are actually met; custom integrations are not official Home Assistant Core Platinum integrations.

## HACS distribution

The standalone repository should contain at minimum:

```text
custom_components/openrouteservice_travel_time/
  __init__.py
  config_flow.py
  const.py
  coordinator.py
  sensor.py
  manifest.json
  strings.json
  translations/en.json

hacs.json
README.md
LICENSE
.github/workflows/validate.yml
tests/
```

Once a stable first version exists:

1. publish GitHub release/tag;
2. install/test as a HACS custom repository;
3. optionally submit it to the HACS default repository later.

## Licence

Recommended licence for the new project: **MIT**.

If any code is copied/adapted from `eifinger/open_route_service`, retain the original MIT copyright notice as required.

A clean modern implementation from API behaviour/docs can instead have its own implementation while acknowledging the older project as prior art.

## Initial development sequence

1. Create the standalone GitHub repository.
2. Scaffold modern custom integration + tests/CI.
3. Implement config flow and API-key validation.
4. Implement entity/fixed-coordinate resolution.
5. Implement `foot-walking` directions first.
6. Expose Duration + Distance.
7. Add reconfigure/reauth and error handling.
8. Validate dynamically with a Home Assistant `person` origin.
9. Validate the duration sensor as a BODS v0.7 walking source.
10. Add cycling/driving profiles after walking is stable.
11. Publish first beta through HACS custom-repository flow.

## Separation from BODS v0.7

The OpenRouteService project can develop concurrently.

BODS v0.7 should not wait for it before continuing unrelated work. When the companion integration produces a trustworthy duration entity, BODS only needs compatibility validation and documentation rather than provider-specific runtime code.
