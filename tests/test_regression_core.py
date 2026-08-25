"""Regression notes/tests for the pure ETA core.

These tests are designed to run in the development workspace where the captured
Morpeth files are available; the large GTFS fixture is deliberately not committed.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from custom_components.bods_bus_tracker.api import (
    ServiceSpec,
    build_gtfs_index,
    make_snapshot,
    parse_siri,
)

LOCAL_TZ = ZoneInfo("Europe/London")


def run_workspace_regression(workspace: Path) -> dict:
    gtfs = workspace / "bods_north_east_gtfs.zip"
    services = [ServiceSpec("ANUM", route, "Arriva Northumbria") for route in ("X14", "X15", "X16", "X18")]
    service_date = datetime(2026, 8, 25, 11, 39, tzinfo=LOCAL_TZ).date()
    trips, info = build_gtfs_index(gtfs, service_date, "3100Z199842", services)
    vehicles = []
    warnings = []
    timestamps = []
    for service in services:
        parsed, timestamp, parsed_warnings = parse_siri(
            (workspace / f"bods_{service.route}.xml").read_bytes(), services
        )
        vehicles.extend(parsed)
        warnings.extend(parsed_warnings)
        if timestamp:
            timestamps.append(timestamp)
    now = max(timestamps)
    snapshot = make_snapshot(
        trips,
        info,
        vehicles,
        now,
        "3100Z199842",
        "The Fairway",
        services,
        {},
        warnings,
        180,
    )
    return snapshot
