# Contributing

Thanks for helping test or improve BODS Bus Tracker.

## Bug reports

Please include:

- Home Assistant version;
- integration version;
- BODS region;
- stop ATCO code;
- route/operator and selected services;
- stop view;
- whether routed walking is enabled and, if relevant, the routing provider/entity type;
- approximate date/time;
- relevant logs and Home Assistant integration diagnostics.

Never include your BODS API key, routing-provider credentials or unredacted precise personal-location data.

For structured v0.6 field testing, see [`TESTING.md`](TESTING.md).

## Pull requests

Please keep changes focused and preserve the generic multi-stop architecture.

Before submitting code changes:

1. Ensure Python files compile.
2. Keep `manifest.json` and `const.py` version values aligned when making a release.
3. Update `CHANGELOG.md` for user-visible changes.
4. Run the repository validation workflow and keep all current gates green: HACS, Hassfest, runtime/manifest version sync, GTFS cache policy, Home Assistant-native tests/coverage and strict mypy.
5. Preserve the provider-neutral routed-walking contract and the conservative live-to-GTFS/terminus matching policy unless the change explicitly targets those behaviours.

The known Morpeth regression case uses stop `3100Z199842` with Arriva North East X14/X15/X16/X18. Large BODS/GTFS fixtures are intentionally not committed to the repository.
