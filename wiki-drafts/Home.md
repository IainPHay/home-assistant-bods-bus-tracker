# BODS Bus Tracker Wiki

Welcome to the extended documentation for **BODS Bus Tracker**.

The repository README remains the main entry point for installation, supported features and HACS users. This Wiki is for the material that benefits from more space: step-by-step setup guides, screenshots, worked examples, automation recipes, beta-validation notes and troubleshooting.

## Start here

- [Setting up routed walking with HERE Travel Time](Setting-up-HERE-Travel-Time)
- [Routed walking providers](Routed-walking-providers)
- [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications)
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
- beta features that need real Home Assistant validation;
- troubleshooting walkthroughs.

## Current stable release

The current stable release is **v0.6.0**.

v0.6 adds provider-neutral routed walking guidance, shared BODS live-feed acquisition, shared/persistent GTFS indexing, faster stop reconfiguration and extensive Home Assistant lifecycle/quality hardening.

The routed-walking feature is deliberately provider-neutral: BODS Bus Tracker only reads a selected Home Assistant duration sensor. It does not store routing-provider credentials or call HERE, Google or another routing provider itself.

## v0.7 beta development

v0.7 builds higher-level passenger guidance on top of the trusted v0.6 ETA/matching engine without weakening the conservative live-to-GTFS policy.

Current beta work includes:

- public monitored-stop coordinates for easier routing-provider setup;
- a native **Catchable bus** sensor;
- an explicit per-stop **Catchable-bus safety margin**;
- privacy-safe catchable/following-departure summaries;
- a reusable **zone-exit catchable-bus notification** blueprint.

The Catchable bus state has passed real Home Assistant validation, including the privacy regression introduced during beta.2 and corrected in beta.3.

The zone-exit blueprint has passed controlled Home Assistant execution and Companion App service-call testing. A genuine physical zone-exit trigger and receipt on the target phone remain the final live gate before the next prerelease is published.

See [Catchable bus and zone-exit notifications](Catchable-bus-and-zone-exit-notifications) for the current beta workflow.

---