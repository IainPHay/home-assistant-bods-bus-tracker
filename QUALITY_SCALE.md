# Integration Quality Scale evidence

This document is the project's evidence map against the Home Assistant Integration Quality Scale.

It is a **project self-audit**, not an official Home Assistant quality-tier award. BODS Bus Tracker is currently a custom/HACS integration. If it is proposed for Home Assistant Core, the same evidence can be used during review, with any Core-specific repository requirements completed at that point.

## Current automated evidence

Current `feature/v0.7` validation:

- **182 tests passed**;
- **99.08% overall integration line coverage**;
- **100% `config_flow.py` coverage**;
- every integration Python module is **above 95%** line coverage;
- HACS validation passes;
- hassfest validation passes;
- strict mypy validation passes for all integration source files;
- manifest/runtime version consistency is checked;
- GTFS cache invalidation has a dedicated regression gate.

CI deliberately enforces the two coverage requirements separately:

1. `config_flow.py` must remain at **100%**;
2. every integration Python module must remain **above 95%**.

The overall project gate is additionally set to **97%** to prevent broad regression.

## Bronze

| Rule | Status | Evidence |
| --- | --- | --- |
| action-setup | Exempt | No custom actions/services are registered. |
| appropriate-polling | Done | `live_feed.py` shares operator requests, de-duplicates in-flight work, caches responses and applies global request spacing. |
| brands | Done for custom integration | Project and component brand assets are present under `brand/` and `custom_components/bods_bus_tracker/brand/`. A future Core submission would follow the then-current official brands-repository process. |
| common-modules | Done | Shared matching, walking, catchability, GTFS and live-feed policy are separated into reusable modules rather than duplicated in platforms. |
| config-flow-test-coverage | Done | `config_flow.py` is at 100% and CI fails if any config-flow line becomes uncovered. Tests cover initial setup, subentries, reconfigure, reauth and HTTP/error recovery paths. |
| config-flow | Done | UI-only account config flow plus bus-stop config subentries; no YAML setup path. |
| dependency-transparency | Done | `manifest.json` has no third-party Python requirements. |
| docs-actions | Exempt | No integration-specific custom actions. |
| docs-conditions | Exempt | No integration-specific custom conditions. |
| docs-high-level-description | Done | README explains BODS, GTFS/SIRI-VM matching and passenger-information scope. |
| docs-installation-instructions | Done | README/HACS installation documentation. |
| docs-removal-instructions | Done | README contains stop-level and full integration removal instructions. |
| docs-triggers | Exempt | No integration-specific trigger platform. Blueprints use ordinary Home Assistant triggers. |
| entity-event-setup | Exempt | Entities are coordinator-backed and do not subscribe directly to external events. |
| entity-unique-id | Done | All sensor/binary-sensor entities have stable unique IDs, including migration compatibility. |
| has-entity-name | Done | Entity classes use `has_entity_name` with translation keys. |
| runtime-data | Done | Typed `BODSBusRuntimeData` is stored on the config entry. |
| test-before-configure | Done | API credentials are validated in config/reauth flows before accepting configuration. |
| test-before-setup | Done | Setup prepares GTFS state and performs the first coordinator refresh before platform setup completes. |
| unique-config-entry | Done | One shared BODS account entry is enforced; monitored stops are subentries. |

## Silver

| Rule | Status | Evidence |
| --- | --- | --- |
| action-exceptions | Exempt | No custom service/entity actions. |
| config-entry-unloading | Done | Platforms unload, in-flight live-feed work is cancelled and shared runtime caches are cleared. |
| docs-configuration-parameters | Done | README, Wiki and translated flow descriptions document stop view, walking, polling and catchable margin options. |
| docs-installation-parameters | Done | API-key requirement and BODS account setup are documented. |
| entity-unavailable | Done | Coordinator/entity availability reflects trusted state; walking/catchability exposes explicit unavailable/non-ok states rather than fabricated values. |
| integration-owner | Done | Manifest codeowner and repository CODEOWNERS identify `@IainPHay`. |
| log-when-unavailable | Done | Coordinator logs degraded/scheduled-only live-feed state and recovery without log spam on unchanged state. |
| parallel-updates | Done | Entity platforms declare `PARALLEL_UPDATES = 0`; shared coordinator/live-feed logic controls upstream concurrency. |
| reauthentication-flow | Done | Confirmed invalid credentials raise `ConfigEntryAuthFailed`; reauth updates the shared key without deleting stops. |
| test-coverage | Done | Current overall coverage is 99.08%; every integration Python module is above 95%, enforced in CI. |

## Gold

| Rule | Status | Evidence |
| --- | --- | --- |
| devices | Done | Each monitored stop is represented as a logical Home Assistant service device. |
| diagnostics | Done | Config-entry diagnostics include useful stop/coordinator state with API-key redaction, coordinate stripping and private guidance scratch-state removal. |
| discovery | Exempt | BODS is a cloud data service; user-selected public transport stops are not network-discoverable devices. |
| discovery-update-info | Exempt | No network address/host discovery information exists to update. |
| docs-data-update | Done | README/Wiki explain BODS polling, HERE/provider polling separation, GTFS refresh/cache behaviour and fallback. |
| docs-examples | Done | Repository and Wiki contain dashboard, terminus, walking and automation examples. |
| docs-known-limitations | Done | README has an explicit limitations section. |
| docs-supported-devices | Exempt | No physical devices are integrated; stops are logical service devices. |
| docs-supported-functions | Done | README entity/features sections document departures, arrivals, timing, walking, catchability and diagnostics. |
| docs-troubleshooting | Done | Wiki contains live-data, routed-walking and provider troubleshooting. |
| docs-use-cases | Done | README/Wiki cover ordinary departure stops, termini, walking guidance and zone-exit catchable-bus notifications. |
| dynamic-devices | Done | Bus-stop config subentries/devices can be added after the BODS account entry is created. |
| entity-category | Done | Diagnostic-only entities use `EntityCategory.DIAGNOSTIC`. |
| entity-device-class | Done | Duration, timestamp and enum entities use appropriate Home Assistant device classes. |
| entity-disabled-by-default | Done | Lower-value high-frequency diagnostic counters are disabled by default. |
| entity-translations | Done | Entity names/states are defined in `translations/en.json`. |
| exception-translations | Done | Setup/update/authentication exceptions use translated Home Assistant keys. |
| icon-translations | Done | `icons.json` provides entity/state icons. |
| reconfiguration-flow | Done | Stop subentries support reconfiguration without delete/re-add. |
| repair-issues | Done | Persistently missing routed-walking source entities create a translated, self-clearing Repair. |
| stale-devices | Done | Device removal is permitted when no current stop subentry owns the service-device identifier. |

## Platinum

| Rule | Status | Evidence |
| --- | --- | --- |
| async-dependency | Done | No blocking external client dependency; HTTP is async and CPU/file/CSV/ZIP work is dispatched to the executor where appropriate. |
| inject-websession | Done | HTTP code uses Home Assistant's shared aiohttp session via `async_get_clientsession`. |
| strict-typing | Done | All integration source files pass the repository's strict mypy gate in CI. |

## Evidence files

Primary implementation/evidence locations:

- `custom_components/bods_bus_tracker/quality_scale.yaml`
- `custom_components/bods_bus_tracker/config_flow.py`
- `custom_components/bods_bus_tracker/coordinator.py`
- `custom_components/bods_bus_tracker/live_feed.py`
- `custom_components/bods_bus_tracker/diagnostics.py`
- `custom_components/bods_bus_tracker/entity.py`
- `custom_components/bods_bus_tracker/sensor.py`
- `custom_components/bods_bus_tracker/binary_sensor.py`
- `custom_components/bods_bus_tracker/translations/en.json`
- `custom_components/bods_bus_tracker/icons.json`
- `tests/`
- `.github/workflows/validate.yml`
- `README.md`, `DYNAMIC_WALKING.md`, `ZONE_EXIT_NOTIFICATION.md` and the project Wiki.

## Remaining work towards an official quality-tier review

There is no known unimplemented rule in the project's current `quality_scale.yaml`: all 54 rules are marked either **done** or **exempt** with a reason.

The remaining distinction is process/evidence rather than a known runtime feature gap:

- keep the new CI gates green as v0.7 evolves;
- keep this evidence map and user documentation synchronized with code;
- continue widening real-world operator/region validation;
- if moving from HACS/custom to Home Assistant Core, satisfy the then-current Core repository, ownership and branding submission requirements and undergo Home Assistant review.

The quality target is therefore **no silent regression**, not artificially forcing 100% overall code coverage with low-value tests.
