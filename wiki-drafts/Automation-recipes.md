# Automation recipes

This page will collect reusable Home Assistant automation patterns built on BODS Bus Tracker state.

## Available now

The repository includes a generic **Leave now notification** blueprint.

See:

https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/blueprints/automation/bods_bus_tracker_leave_now.yaml

## Planned examples

The v0.7 roadmap includes:

- notify a traveller when they leave a zone with the first bus they can realistically catch;
- include the following scheduled departure as a fallback;
- optionally notify a second person;
- infer possible boarding only after enough evidence exists;
- calculate expected arrival and journey-state notifications.

These will not be treated as trusted automations until the underlying state has been validated.
