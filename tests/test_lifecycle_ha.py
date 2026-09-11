"""Home Assistant lifecycle and Repairs tests for BODS Bus Tracker."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker import (
    BODSBusRuntimeData,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.bods_bus_tracker.const import (
    CACHE_DIR,
    CONF_API_KEY,
    CONF_DYNAMIC_WALKING_TIME,
    CONF_LEGACY_ENTITY_IDS,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_VIEW,
    CONF_WALKING_TIME,
    CONF_WALKING_TIME_ENTITY,
    DOMAIN,
    STOP_VIEW_DEPARTURES,
    SUBENTRY_TYPE_STOP,
    WALKING_ISSUE_PREFIX,
)
from custom_components.bods_bus_tracker.coordinator import BODSBusCoordinator


STOP_DATA = {
    CONF_REGION: "north_east",
    CONF_STOP_ATCO: "3100Z199842",
    CONF_STOP_NAME: "The Fairway",
    CONF_SERVICES: ["ANUM|X14", "ANUM|X18"],
    CONF_STOP_VIEW: STOP_VIEW_DEPARTURES,
    CONF_WALKING_TIME: 5,
    CONF_DYNAMIC_WALKING_TIME: False,
    CONF_WALKING_TIME_ENTITY: "",
    CONF_POLL_INTERVAL: 30,
}


def _entry_with_stop(
    *,
    dynamic: bool = False,
    walking_entity: str = "",
) -> MockConfigEntry:
    data = {
        **STOP_DATA,
        CONF_DYNAMIC_WALKING_TIME: dynamic,
        CONF_WALKING_TIME_ENTITY: walking_entity,
    }
    return MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "test-key"},
        version=2,
        subentries_data=[
            ConfigSubentryData(
                data=data,
                subentry_id="fairway-stop",
                subentry_type=SUBENTRY_TYPE_STOP,
                title="The Fairway (3100Z199842)",
                unique_id="north_east:3100Z199842",
            )
        ],
    )


async def test_migrate_legacy_entry(hass) -> None:
    """Legacy one-stop entries migrate to account + stop subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="The Fairway",
        data={
            CONF_API_KEY: "legacy-key",
            CONF_REGION: "north_east",
            CONF_STOP_ATCO: "3100Z199842",
            CONF_STOP_NAME: "The Fairway",
            CONF_SERVICES: ["ANUM|X14"],
        },
        options={CONF_POLL_INTERVAL: 60},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 2
    assert entry.title == "BODS Bus Tracker"
    assert entry.data == {CONF_API_KEY: "legacy-key"}
    assert len(entry.subentries) == 1

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_STOP_ATCO] == "3100Z199842"
    assert subentry.data[CONF_POLL_INTERVAL] == 60
    assert subentry.data[CONF_LEGACY_ENTITY_IDS] is True


async def test_migrate_legacy_entry_missing_required_data(hass) -> None:
    """Broken legacy data fails migration safely."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Broken",
        data={CONF_API_KEY: "legacy-key"},
        version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is False


async def test_setup_entry_prepares_every_stop(hass) -> None:
    """Setup builds shared regional runtime data and first-refreshes each stop."""
    entry = _entry_with_stop()
    entry.add_to_hass(hass)

    live_feed = MagicMock()
    timetable = MagicMock()
    coordinator = MagicMock()
    coordinator.async_prepare = AsyncMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.bods_bus_tracker.BODSLiveFeedClient",
            return_value=live_feed,
        ),
        patch(
            "custom_components.bods_bus_tracker.SharedGTFSRegionIndex",
            return_value=timetable,
        ) as timetable_cls,
        patch(
            "custom_components.bods_bus_tracker.BODSBusCoordinator",
            return_value=coordinator,
        ) as coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
    ):
        assert await async_setup_entry(hass, entry) is True

    timetable_cls.assert_called_once()
    coordinator_cls.assert_called_once()
    coordinator.async_prepare.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    forward.assert_awaited_once()
    assert entry.runtime_data.live_feed is live_feed
    assert entry.runtime_data.coordinators["fairway-stop"] is coordinator
    assert entry.runtime_data.timetables["north_east"] is timetable


async def test_unload_entry_cleans_runtime(hass) -> None:
    """Successful unload cancels live work and releases runtime maps."""
    entry = _entry_with_stop()
    entry.add_to_hass(hass)
    live_feed = MagicMock()
    live_feed.async_close = AsyncMock()
    entry.runtime_data = BODSBusRuntimeData(
        coordinators={"fairway-stop": MagicMock()},
        live_feed=live_feed,
        timetables={"north_east": MagicMock()},
    )

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry) is True

    live_feed.async_close.assert_awaited_once()
    assert entry.runtime_data.coordinators == {}
    assert entry.runtime_data.timetables == {}


async def test_failed_unload_preserves_runtime(hass) -> None:
    """Runtime state is retained when a platform refuses to unload."""
    entry = _entry_with_stop()
    entry.add_to_hass(hass)
    live_feed = MagicMock()
    live_feed.async_close = AsyncMock()
    coordinators = {"fairway-stop": MagicMock()}
    entry.runtime_data = BODSBusRuntimeData(
        coordinators=coordinators.copy(),
        live_feed=live_feed,
        timetables={"north_east": MagicMock()},
    )

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=False),
    ):
        assert await async_unload_entry(hass, entry) is False

    live_feed.async_close.assert_not_awaited()
    assert entry.runtime_data.coordinators


async def test_remove_entry_deletes_cache_and_repairs(hass) -> None:
    """Deleting the integration removes persistent cache data and Repairs."""
    entry = _entry_with_stop()
    entry.add_to_hass(hass)

    cache = Path(hass.config.path(CACHE_DIR))
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "test.txt").write_text("cached", encoding="utf-8")

    issue_id = f"{WALKING_ISSUE_PREFIX}fairway-stop"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="walking_time_entity_missing",
        translation_placeholders={
            "entity_id": "sensor.missing",
            "stop": "The Fairway",
        },
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    await async_remove_entry(hass, entry)

    assert not cache.exists()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_stale_device_removal_policy(hass) -> None:
    """Current stop devices are retained while orphan devices may be removed."""
    entry = _entry_with_stop()
    entry.add_to_hass(hass)

    current = SimpleNamespace(
        identifiers={(DOMAIN, f"{entry.entry_id}:fairway-stop")}
    )
    orphan = SimpleNamespace(identifiers={(DOMAIN, f"{entry.entry_id}:old-stop")})

    assert await async_remove_config_entry_device(hass, entry, current) is False
    assert await async_remove_config_entry_device(hass, entry, orphan) is True


async def test_missing_dynamic_walking_entity_creates_and_clears_repair(hass) -> None:
    """A genuinely missing routed-walking source raises one actionable Repair."""
    entry = _entry_with_stop(
        dynamic=True,
        walking_entity="sensor.walk_to_fairway",
    )
    entry.add_to_hass(hass)
    subentry = next(iter(entry.subentries.values()))

    coordinator = BODSBusCoordinator(
        hass,
        entry,
        subentry,
        MagicMock(),
        MagicMock(),
    )

    # The Repair is deliberately delayed until the integration is running and
    # the entity has been confirmed missing on a second coordinator pass.
    first = coordinator._walking_guidance_values(
        __import__("datetime").datetime.now(coordinator.update_interval.__class__.__module__ and __import__("zoneinfo").ZoneInfo("Europe/London"))
    )
    second = coordinator._walking_guidance_values(
        __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("Europe/London"))
    )
    assert first[1] == "static_fallback"
    assert second[4] == "missing"

    issue_id = f"{WALKING_ISSUE_PREFIX}{subentry.subentry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(
        "sensor.walk_to_fairway",
        "6.2",
        {"unit_of_measurement": "min"},
    )
    dynamic = coordinator._walking_guidance_values(
        __import__("datetime").datetime.now(__import__("zoneinfo").ZoneInfo("Europe/London"))
    )

    assert dynamic[0] == 7
    assert dynamic[1] == "dynamic"
    assert dynamic[4] == "ok"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
