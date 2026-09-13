# Testing a new operator or region

Cross-operator and cross-region testing is especially valuable for v0.6.

The full structured checklist is maintained in the repository:

https://github.com/IainPHay/home-assistant-bods-bus-tracker/blob/main/TESTING.md

Useful reports include both successes and failures.

Please include:

- Home Assistant version;
- BODS Bus Tracker version;
- BODS region;
- stop name and ATCO/NaPTAN code;
- operator and selected services;
- stop view;
- whether routed walking is enabled;
- approximate test time;
- Data status / live vehicles / GTFS matches;
- whether a problem recovered without reconfiguration.

Never include your BODS API key.
