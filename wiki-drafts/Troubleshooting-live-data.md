# Troubleshooting live data

BODS live data can vary by operator and can occasionally be unavailable even when timetable data remain healthy.

## Data status

Useful states include:

- **OK** — normal live/timetable processing is healthy;
- **Scheduled only** — timetable fallback is available but live vehicle data are currently unavailable/unusable;
- **Degraded** — partial live-data problem.

An individual service can still be timetable-only while overall **Data status** is OK.

## First checks

1. Open the stop device.
2. Check **Data status**.
3. Check **Live vehicles**.
4. Check **GTFS matches**.
5. Check **Last update**.
6. Go to **Settings → System → Logs** and search for BODS.

## Do not immediately delete the integration

Temporary upstream failures are designed to fall back to timetable data and recover automatically.

During v0.6 validation, short live-feed failures were observed to recover without reconfiguration.

## Authentication

v0.6 distinguishes between:

- a confirmed invalid BODS token;
- an ordinary/transient HTTP 403 access failure;
- HTTP 429 rate limiting;
- timeout/connection failure.

A confirmed invalid token can trigger Home Assistant reauthentication.

An ordinary 403 should not force a misleading credential prompt.

## Diagnostics

If reporting a problem, download Home Assistant integration diagnostics and review the file before posting it.

Do not post:

- the BODS API key;
- routing-provider credentials;
- unredacted precise personal-location information.
