# Contributing

Thanks for helping test or improve BODS Bus Tracker.

## Bug reports

Please include:

- Home Assistant version;
- integration version;
- BODS region;
- stop ATCO code;
- route/operator;
- approximate date/time;
- relevant logs and Home Assistant integration diagnostics.

Never include your BODS API key.

## Pull requests

Please keep changes focused and preserve the generic multi-stop architecture.

Before submitting code changes:

1. Ensure Python files compile.
2. Keep `manifest.json` and `const.py` version values aligned when making a release.
3. Update `CHANGELOG.md` for user-visible changes.
4. Run/allow the HACS and Hassfest validation workflows.

The known Morpeth regression case uses stop `3100Z199842` with Arriva North East X14/X15/X16/X18. Large BODS/GTFS fixtures are intentionally not committed to the repository.
