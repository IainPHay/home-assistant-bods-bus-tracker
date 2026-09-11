"""Pure GTFS parsed-index cache validation policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

GTFS_INDEX_CACHE_SCHEMA = 1


def cache_matches_inputs(
    payload: Mapping[str, object],
    fingerprint: Mapping[str, int],
    service_date_iso: str,
    service_keys: Sequence[str],
) -> bool:
    """Return True only when every cache-defining input still matches."""
    if payload.get("schema") != GTFS_INDEX_CACHE_SCHEMA:
        return False
    if payload.get("gtfs") != dict(fingerprint):
        return False
    if payload.get("service_date") != service_date_iso:
        return False

    cached_services = payload.get("services")
    if not isinstance(cached_services, list):
        return False
    return tuple(cached_services) == tuple(service_keys)
