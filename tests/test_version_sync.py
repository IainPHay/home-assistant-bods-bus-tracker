"""Release version consistency tests."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.bods_bus_tracker.const import VERSION


def test_manifest_and_runtime_versions_match() -> None:
    """The device software version must match the HACS/manifest version."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "custom_components" / "bods_bus_tracker" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert VERSION == manifest["version"]
