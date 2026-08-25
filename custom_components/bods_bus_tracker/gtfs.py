"""GTFS cache and download helpers for BODS Bus Tracker."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import validate_gtfs
from .const import CACHE_DIR, DEFAULT_GTFS_REFRESH_HOURS, GTFS_URL_TEMPLATE, VERSION

_LOGGER = logging.getLogger(__name__)
_REGION_LOCKS: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


class GTFSDownloadError(Exception):
    """Raised when a GTFS region cannot be downloaded or validated."""


def gtfs_path(hass: HomeAssistant, region: str) -> Path:
    return Path(hass.config.path(CACHE_DIR, f"{region}.zip"))


def _is_cache_fresh(path: Path, refresh_hours: float) -> bool:
    if not path.exists():
        return False
    validate_gtfs(path)
    age_hours = (time.time() - path.stat().st_mtime) / 3600.0
    return age_hours < refresh_hours


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=".gtfs-", suffix=".zip", delete=False
        ) as temp_file:
            temp_name = temp_file.name
            temp_file.write(data)
        temp_path = Path(temp_name)
        validate_gtfs(temp_path)
        os.replace(temp_path, path)
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


async def async_ensure_gtfs(
    hass: HomeAssistant,
    region: str,
    *,
    refresh_hours: float = DEFAULT_GTFS_REFRESH_HOURS,
) -> Path:
    """Return a valid cached regional GTFS, downloading if required."""
    path = gtfs_path(hass, region)
    async with _REGION_LOCKS[region]:
        try:
            fresh = await hass.async_add_executor_job(_is_cache_fresh, path, refresh_hours)
        except Exception:
            fresh = False
        if fresh:
            return path

        url = GTFS_URL_TEMPLATE.format(region=region)
        session = async_get_clientsession(hass)
        try:
            async with session.get(
                url,
                timeout=ClientTimeout(total=180),
                headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
            ) as response:
                response.raise_for_status()
                data = await response.read()
            await hass.async_add_executor_job(_atomic_write, path, data)
            return path
        except (ClientError, ClientResponseError, TimeoutError, ValueError, OSError) as exc:
            _LOGGER.warning("Unable to refresh BODS GTFS region %s: %s", region, exc)
            try:
                await hass.async_add_executor_job(validate_gtfs, path)
            except Exception as cache_exc:
                raise GTFSDownloadError(
                    f"Unable to download a valid GTFS feed for region {region}"
                ) from cache_exc
            return path
