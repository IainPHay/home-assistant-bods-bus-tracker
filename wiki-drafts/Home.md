# BODS Bus Tracker Wiki

Welcome to the extended documentation for **BODS Bus Tracker**.

The repository README remains the main entry point for installation, supported features and HACS users. This Wiki is intended for the extra material that benefits from more space: step-by-step setup guides, screenshots, worked examples, automation recipes and troubleshooting.

## Start here

- [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time)
- [Routed walking providers](Routed-walking-providers)
- [Dashboard examples](Dashboard-examples)
- [Automation recipes](Automation-recipes)
- [Terminus setup](Terminus-setup)
- [Troubleshooting live data](Troubleshooting-live-data)
- [Testing a new operator or region](Testing-a-new-operator-or-region)

## Documentation model

Use the repository README for:

- installation;
- the current stable feature summary;
- entity overview;
- compatibility requirements;
- release/version information.

Use this Wiki for:

- detailed provider setup;
- screenshots and worked examples;
- advanced automations;
- troubleshooting walkthroughs;
- examples that can evolve without making the HACS README too large.

## Current stable release

The current stable release is **v0.6.0**.

v0.6 adds provider-neutral routed walking guidance, shared BODS live-feed acquisition, shared/persistent GTFS indexing, faster stop reconfiguration and extensive Home Assistant lifecycle/quality hardening.

The routed-walking feature is deliberately provider-neutral: BODS Bus Tracker only reads a selected Home Assistant duration sensor. It does not store routing-provider credentials or call HERE/Google itself.
