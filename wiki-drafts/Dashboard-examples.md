# Dashboard examples

BODS Bus Tracker includes stock Home Assistant Markdown-card examples for:

- an ordinary boarding stop;
- a terminus/bus station.

The repository examples are the canonical YAML:

- https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/example_dashboard_card.yaml
- https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/example_terminus_card.yaml

## Routed walking

The cards are provider-neutral.

They read the effective walking and leave-guidance attributes from the BODS **Next bus** entity. They do not need to know whether the source was:

- static walking;
- HERE;
- another routed provider;
- static fallback after a provider problem.

More worked dashboard examples can be added here as users test v0.6 on additional layouts.
