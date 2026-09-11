"""GTFS parsed-index cache invalidation regression tests."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "bods_bus_tracker"
    / "gtfs_cache_model.py"
)
SPEC = importlib.util.spec_from_file_location("gtfs_cache_model_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

cache_matches_inputs = MODULE.cache_matches_inputs
GTFS_INDEX_CACHE_SCHEMA = MODULE.GTFS_INDEX_CACHE_SCHEMA


class GTFSCachePolicyTests(unittest.TestCase):
    """Validate every input that must invalidate the persistent parsed index."""

    def setUp(self) -> None:
        self.fingerprint = {"size": 123456, "mtime_ns": 987654321}
        self.service_date = "2026-09-11"
        self.services = ("ANUM|X14", "ANUM|X15", "ANUM|X16", "ANUM|X18")
        self.payload = {
            "schema": GTFS_INDEX_CACHE_SCHEMA,
            "gtfs": dict(self.fingerprint),
            "service_date": self.service_date,
            "services": list(self.services),
        }

    def test_exact_inputs_reuse_cache(self) -> None:
        self.assertTrue(
            cache_matches_inputs(
                self.payload,
                self.fingerprint,
                self.service_date,
                self.services,
            )
        )

    def test_gtfs_file_change_invalidates_cache(self) -> None:
        changed = dict(self.fingerprint)
        changed["mtime_ns"] += 1
        self.assertFalse(
            cache_matches_inputs(
                self.payload,
                changed,
                self.service_date,
                self.services,
            )
        )

    def test_service_date_change_invalidates_cache(self) -> None:
        self.assertFalse(
            cache_matches_inputs(
                self.payload,
                self.fingerprint,
                "2026-09-12",
                self.services,
            )
        )

    def test_service_set_change_invalidates_cache(self) -> None:
        self.assertFalse(
            cache_matches_inputs(
                self.payload,
                self.fingerprint,
                self.service_date,
                (*self.services, "ANUM|X20"),
            )
        )

    def test_schema_change_invalidates_cache(self) -> None:
        payload = dict(self.payload)
        payload["schema"] = GTFS_INDEX_CACHE_SCHEMA + 1
        self.assertFalse(
            cache_matches_inputs(
                payload,
                self.fingerprint,
                self.service_date,
                self.services,
            )
        )


if __name__ == "__main__":
    unittest.main()
