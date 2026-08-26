from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected exactly one match in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------------------------------------------------------------------------
# Constants / platforms
# ---------------------------------------------------------------------------
const = ROOT / "custom_components/bods_bus_tracker/const.py"
replace_once(
    const,
    'PLATFORMS = ["sensor"]',
    'PLATFORMS = ["sensor", "binary_sensor"]',
)
replace_once(
    const,
    'CONF_LEGACY_ENTITY_IDS = "legacy_entity_ids"\n',
    'CONF_LEGACY_ENTITY_IDS = "legacy_entity_ids"\nCONF_WALKING_TIME = "walking_time"\n',
)
replace_once(
    const,
    'DEFAULT_POLL_INTERVAL = 30\nMIN_POLL_INTERVAL = 15\nMAX_POLL_INTERVAL = 300\n',
    'DEFAULT_POLL_INTERVAL = 30\nMIN_POLL_INTERVAL = 15\nMAX_POLL_INTERVAL = 300\n'
    'DEFAULT_WALKING_TIME = 0\nMIN_WALKING_TIME = 0\nMAX_WALKING_TIME = 120\n',
)

# ---------------------------------------------------------------------------
# Config flow: walking time is stored independently for each stop.
# 0 minutes means the optional leave guidance is disabled.
# ---------------------------------------------------------------------------
flow = ROOT / "custom_components/bods_bus_tracker/config_flow.py"
replace_once(
    flow,
    '    CONF_STOP_SELECTION,\n    DEFAULT_POLL_INTERVAL,\n    DOMAIN,\n    MAX_POLL_INTERVAL,\n    MIN_POLL_INTERVAL,\n',
    '    CONF_STOP_SELECTION,\n    CONF_WALKING_TIME,\n    DEFAULT_POLL_INTERVAL,\n'
    '    DEFAULT_WALKING_TIME,\n    DOMAIN,\n    MAX_POLL_INTERVAL,\n'
    '    MAX_WALKING_TIME,\n    MIN_POLL_INTERVAL,\n    MIN_WALKING_TIME,\n',
)
replace_once(
    flow,
    '                    self._data[CONF_SERVICES] = selected\n'
    '                    self._data[CONF_POLL_INTERVAL] = int(\n'
    '                        user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)\n'
    '                    )\n',
    '                    self._data[CONF_SERVICES] = selected\n'
    '                    self._data[CONF_WALKING_TIME] = int(\n'
    '                        user_input.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)\n'
    '                    )\n'
    '                    self._data[CONF_POLL_INTERVAL] = int(\n'
    '                        user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)\n'
    '                    )\n',
)
replace_once(
    flow,
    '                    vol.Optional(\n'
    '                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL\n'
    '                    ): selector.NumberSelector(\n',
    '                    vol.Optional(\n'
    '                        CONF_WALKING_TIME, default=DEFAULT_WALKING_TIME\n'
    '                    ): selector.NumberSelector(\n'
    '                        selector.NumberSelectorConfig(\n'
    '                            min=MIN_WALKING_TIME,\n'
    '                            max=MAX_WALKING_TIME,\n'
    '                            step=1,\n'
    '                            mode=selector.NumberSelectorMode.BOX,\n'
    '                            unit_of_measurement="min",\n'
    '                        )\n'
    '                    ),\n'
    '                    vol.Optional(\n'
    '                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL\n'
    '                    ): selector.NumberSelector(\n',
)
replace_once(
    flow,
    '        """Change services and poll interval for one existing stop."""',
    '        """Change services, walking time and poll interval for one stop."""',
)
replace_once(
    flow,
    '                            CONF_SERVICES: selected,\n'
    '                            CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),\n',
    '                            CONF_SERVICES: selected,\n'
    '                            CONF_WALKING_TIME: int(user_input[CONF_WALKING_TIME]),\n'
    '                            CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),\n',
)
replace_once(
    flow,
    '                    vol.Required(\n'
    '                        CONF_POLL_INTERVAL,\n'
    '                        default=int(\n'
    '                            subentry.data.get(\n'
    '                                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL\n'
    '                            )\n'
    '                        ),\n'
    '                    ): selector.NumberSelector(\n',
    '                    vol.Required(\n'
    '                        CONF_WALKING_TIME,\n'
    '                        default=int(\n'
    '                            subentry.data.get(\n'
    '                                CONF_WALKING_TIME, DEFAULT_WALKING_TIME\n'
    '                            )\n'
    '                        ),\n'
    '                    ): selector.NumberSelector(\n'
    '                        selector.NumberSelectorConfig(\n'
    '                            min=MIN_WALKING_TIME,\n'
    '                            max=MAX_WALKING_TIME,\n'
    '                            step=1,\n'
    '                            mode=selector.NumberSelectorMode.BOX,\n'
    '                            unit_of_measurement="min",\n'
    '                        )\n'
    '                    ),\n'
    '                    vol.Required(\n'
    '                        CONF_POLL_INTERVAL,\n'
    '                        default=int(\n'
    '                            subentry.data.get(\n'
    '                                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL\n'
    '                            )\n'
    '                        ),\n'
    '                    ): selector.NumberSelector(\n',
)

# ---------------------------------------------------------------------------
# Pure walking calculation helper. This deliberately sits outside the ETA
# engine: it consumes the already-trusted expected time and never changes it.
# ---------------------------------------------------------------------------
walking = ROOT / "custom_components/bods_bus_tracker/walking.py"
walking.write_text(
    '''"""Walking-time guidance for BODS Bus Tracker."""\n\n'
    'from __future__ import annotations\n\n'
    'import math\n'
    'from datetime import datetime, timedelta\n'
    'from typing import Any\n\n\n'
    'def apply_walking_guidance(\n'
    '    snapshot: dict[str, Any], now: datetime, walking_minutes: int\n'
    ') -> dict[str, Any]:\n'
    '    """Add leave-by guidance without changing the underlying ETA."""\n'
    '    next_bus = snapshot.get("next_bus")\n'
    '    if not isinstance(next_bus, dict):\n'
    '        return snapshot\n\n'
    '    walking_minutes = max(0, int(walking_minutes))\n'
    '    next_bus["walking_minutes"] = walking_minutes\n'
    '    next_bus["leave_by"] = None\n'
    '    next_bus["leave_in_minutes"] = None\n'
    '    next_bus["leave_now"] = False\n\n'
    '    if walking_minutes <= 0 or not next_bus.get("available"):\n'
    '        return snapshot\n\n'
    '    expected_value = next_bus.get("expected")\n'
    '    if not expected_value:\n'
    '        return snapshot\n\n'
    '    try:\n'
    '        expected = datetime.fromisoformat(str(expected_value))\n'
    '    except (TypeError, ValueError):\n'
    '        return snapshot\n\n'
    '    if expected.tzinfo is None and now.tzinfo is not None:\n'
    '        expected = expected.replace(tzinfo=now.tzinfo)\n\n'
    '    leave_by = expected - timedelta(minutes=walking_minutes)\n'
    '    next_bus["leave_by"] = leave_by.isoformat()\n\n'
    '    # Once the expected bus time has passed, guidance for that departure is\n'
    '    # no longer actionable. The next coordinator refresh will naturally move\n'
    '    # on to the next departure when the ETA engine does.\n'
    '    if now >= expected:\n'
    '        return snapshot\n\n'
    '    seconds_until_leave = (leave_by - now).total_seconds()\n'
    '    if seconds_until_leave <= 0:\n'
    '        next_bus["leave_in_minutes"] = 0\n'
    '        next_bus["leave_now"] = True\n'
    '    else:\n'
    '        next_bus["leave_in_minutes"] = max(1, math.ceil(seconds_until_leave / 60))\n\n'
    '    return snapshot\n'''.replace("'\n    '", ""),
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# Coordinator consumes the walking setting after make_snapshot().
# ---------------------------------------------------------------------------
coord = ROOT / "custom_components/bods_bus_tracker/coordinator.py"
replace_once(
    coord,
    '    CONF_STOP_NAME,\n    DEFAULT_POLL_INTERVAL,\n',
    '    CONF_STOP_NAME,\n    CONF_WALKING_TIME,\n    DEFAULT_POLL_INTERVAL,\n'
    '    DEFAULT_WALKING_TIME,\n',
)
replace_once(
    coord,
    'from .gtfs import async_ensure_gtfs\n',
    'from .gtfs import async_ensure_gtfs\nfrom .walking import apply_walking_guidance\n',
)
replace_once(
    coord,
    '        self.stop_name: str = subentry.data[CONF_STOP_NAME]\n'
    '        self.services: list[ServiceSpec] = [\n',
    '        self.stop_name: str = subentry.data[CONF_STOP_NAME]\n'
    '        self.walking_time: int = int(\n'
    '            subentry.data.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)\n'
    '        )\n'
    '        self.services: list[ServiceSpec] = [\n',
)
replace_once(
    coord,
    '        return await self.hass.async_add_executor_job(\n'
    '            make_snapshot,\n'
    '            self._trips,\n'
    '            self._gtfs_info,\n'
    '            vehicles,\n'
    '            now,\n'
    '            self.stop_atco,\n'
    '            self.stop_name,\n'
    '            self.services,\n'
    '            route_errors,\n'
    '            warnings,\n'
    '            MAX_LIVE_AGE_SECONDS,\n'
    '        )\n',
    '        snapshot = await self.hass.async_add_executor_job(\n'
    '            make_snapshot,\n'
    '            self._trips,\n'
    '            self._gtfs_info,\n'
    '            vehicles,\n'
    '            now,\n'
    '            self.stop_atco,\n'
    '            self.stop_name,\n'
    '            self.services,\n'
    '            route_errors,\n'
    '            warnings,\n'
    '            MAX_LIVE_AGE_SECONDS,\n'
    '        )\n'
    '        return apply_walking_guidance(snapshot, now, self.walking_time)\n',
)

# ---------------------------------------------------------------------------
# Sensors: timestamp + countdown. The binary sensor below is intended for
# automations and toggles when the configured walk should begin.
# ---------------------------------------------------------------------------
sensor = ROOT / "custom_components/bods_bus_tracker/sensor.py"
replace_once(
    sensor,
    '\n\nclass ServiceSensor(BODSBusBaseEntity):\n',
    '''\n\nclass LeaveInSensor(BODSBusBaseEntity):\n    """Minutes remaining until the user should leave for the next bus."""\n\n    _attr_icon = "mdi:walk"\n    _attr_native_unit_of_measurement = UnitOfTime.MINUTES\n\n    def __init__(self, coordinator, entry, subentry) -> None:\n        super().__init__(coordinator, entry, subentry, "leave_in", "Leave in")\n\n    @property\n    def native_value(self):\n        return self.coordinator.data.get("next_bus", {}).get("leave_in_minutes")\n\n    @property\n    def extra_state_attributes(self) -> dict[str, Any]:\n        data = self.coordinator.data.get("next_bus", {})\n        return {\n            "walking_minutes": data.get("walking_minutes"),\n            "leave_by": data.get("leave_by"),\n            "expected": data.get("expected"),\n            "route": data.get("route"),\n        }\n\n\nclass ServiceSensor(BODSBusBaseEntity):\n''',
)
replace_once(
    sensor,
    '        NextBusDelaySensor(coordinator, entry, subentry),\n'
    '        NextBusTimingSensor(coordinator, entry, subentry),\n'
    '    ]\n',
    '        NextBusDelaySensor(coordinator, entry, subentry),\n'
    '        NextBusTimingSensor(coordinator, entry, subentry),\n'
    '        NextBusTimestampSensor(\n'
    '            coordinator,\n'
    '            entry,\n'
    '            subentry,\n'
    '            "leave_by",\n'
    '            "leave_by",\n'
    '            "Leave by",\n'
    '            "mdi:walk",\n'
    '        ),\n'
    '        LeaveInSensor(coordinator, entry, subentry),\n'
    '    ]\n',
)

binary_sensor = ROOT / "custom_components/bods_bus_tracker/binary_sensor.py"
binary_sensor.write_text(
    '''"""Binary sensors for BODS Bus Tracker."""\n\nfrom __future__ import annotations\n\nfrom typing import Any\n\nfrom homeassistant.components.binary_sensor import BinarySensorEntity\nfrom homeassistant.config_entries import ConfigSubentry\nfrom homeassistant.core import HomeAssistant\nfrom homeassistant.helpers.device_registry import DeviceInfo\nfrom homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback\nfrom homeassistant.helpers.update_coordinator import CoordinatorEntity\n\nfrom . import BODSBusConfigEntry\nfrom .const import CONF_LEGACY_ENTITY_IDS, DOMAIN, SUBENTRY_TYPE_STOP, VERSION\nfrom .coordinator import BODSBusCoordinator\n\n\nclass LeaveNowBinarySensor(CoordinatorEntity[BODSBusCoordinator], BinarySensorEntity):\n    """Turn on when it is time to start walking to the selected stop."""\n\n    _attr_has_entity_name = True\n    _attr_name = "Leave now"\n    _attr_icon = "mdi:walk"\n\n    def __init__(\n        self,\n        coordinator: BODSBusCoordinator,\n        entry: BODSBusConfigEntry,\n        subentry: ConfigSubentry,\n    ) -> None:\n        super().__init__(coordinator)\n        self._entry = entry\n        self._subentry = subentry\n        if subentry.data.get(CONF_LEGACY_ENTITY_IDS):\n            self._attr_unique_id = f"{entry.entry_id}_leave_now"\n            self._device_identifier = entry.entry_id\n        else:\n            self._attr_unique_id = (\n                f"{entry.entry_id}_{subentry.subentry_id}_leave_now"\n            )\n            self._device_identifier = f"{entry.entry_id}:{subentry.subentry_id}"\n\n    @property\n    def device_info(self) -> DeviceInfo:\n        return DeviceInfo(\n            identifiers={(DOMAIN, self._device_identifier)},\n            name=self._subentry.title,\n            manufacturer="UK Department for Transport",\n            model="BODS + GTFS bus ETA",\n            sw_version=VERSION,\n            configuration_url="https://data.bus-data.dft.gov.uk/",\n        )\n\n    @property\n    def available(self) -> bool:\n        data = self.coordinator.data.get("next_bus", {})\n        return (\n            super().available\n            and bool(data.get("available"))\n            and int(data.get("walking_minutes") or 0) > 0\n            and bool(data.get("leave_by"))\n        )\n\n    @property\n    def is_on(self) -> bool | None:\n        if not self.available:\n            return None\n        return bool(self.coordinator.data.get("next_bus", {}).get("leave_now"))\n\n    @property\n    def extra_state_attributes(self) -> dict[str, Any]:\n        data = self.coordinator.data.get("next_bus", {})\n        return {\n            "walking_minutes": data.get("walking_minutes"),\n            "leave_by": data.get("leave_by"),\n            "leave_in_minutes": data.get("leave_in_minutes"),\n            "expected": data.get("expected"),\n            "route": data.get("route"),\n            "destination": data.get("destination"),\n        }\n\n\nasync def async_setup_entry(\n    hass: HomeAssistant,\n    entry: BODSBusConfigEntry,\n    async_add_entities: AddConfigEntryEntitiesCallback,\n) -> None:\n    """Set up the per-stop Leave now binary sensor."""\n    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STOP):\n        coordinator = entry.runtime_data.coordinators.get(subentry.subentry_id)\n        if coordinator is None:\n            continue\n        async_add_entities(\n            [LeaveNowBinarySensor(coordinator, entry, subentry)],\n            config_subentry_id=subentry.subentry_id,\n        )\n''',
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# Translation strings
# ---------------------------------------------------------------------------
translation = ROOT / "custom_components/bods_bus_tracker/translations/en.json"
data = json.loads(translation.read_text(encoding="utf-8"))
services = data["config_subentries"]["stop"]["step"]["services"]
services["data"]["walking_time"] = "Walking time to stop"
services["data_description"]["walking_time"] = (
    "Minutes needed to walk from your usual starting point to this boarding stop. "
    "Set to 0 to disable Leave by/Leave now guidance. Include any personal margin you want."
)
reconfigure = data["config_subentries"]["stop"]["step"]["reconfigure"]
reconfigure["description"] = (
    "Change the services, walking time and polling interval for {stop_name} ({stop_atco}). "
    "To monitor a different boarding point, add another stop and remove this one."
)
reconfigure["data"]["walking_time"] = "Walking time to stop"
reconfigure["data_description"]["walking_time"] = (
    "Minutes needed to walk from your usual starting point to this boarding stop. "
    "Set to 0 to disable Leave by/Leave now guidance."
)
translation.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# Generic branch card: show walking guidance only when configured.
# ---------------------------------------------------------------------------
card = ROOT / "example_dashboard_card.yaml"
replace_once(
    card,
    '  {% if next_source == \'live\' and next.get(\'vehicle\') %}\n'
    '  Vehicle {{ next.get(\'vehicle\') }}\n'
    '  {% endif %}\n\n'
    '  ---\n',
    '  {% if next_source == \'live\' and next.get(\'vehicle\') %}\n'
    '  Vehicle {{ next.get(\'vehicle\') }}\n'
    '  {% endif %}\n\n'
    '  {% if next.get(\'leave_by\') %}\n'
    '  {% if next.get(\'leave_now\', false) %}\n'
    '  🚶 <font color="#d32f2f">**Leave now**</font> · {{ next.get(\'walking_minutes\') }} min walk\n'
    '  {% elif next.get(\'leave_in_minutes\') is not none %}\n'
    '  🚶 Leave in **{{ next.get(\'leave_in_minutes\') }} min** · leave by **{{ as_timestamp(next.get(\'leave_by\')) | timestamp_custom(\'%H:%M\', true) }}**\n'
    '  {% endif %}\n'
    '  {% endif %}\n\n'
    '  ---\n',
)

# ---------------------------------------------------------------------------
# Branch documentation. README edits are deliberately minimal and preserve
# the current main-branch wording as the base.
# ---------------------------------------------------------------------------
dash = ROOT / "DASHBOARD_CARD.md"
replace_once(
    dash,
    '- Vehicle ID for the headline service when a live match is available.\n',
    '- Vehicle ID for the headline service when a live match is available.\n'
    '- Optional `Leave in` / `Leave now` guidance when a walking time is configured for the stop.\n',
)

readme = ROOT / "README.md"
replace_once(
    readme,
    '- Configurable live polling interval per stop.\n',
    '- Configurable live polling interval per stop.\n'
    '- Optional per-stop walking time with **Leave by**, **Leave in** and automation-friendly **Leave now** entities.\n',
)
replace_once(
    readme,
    '7. Choose the live polling interval. **30 seconds** is recommended.\n',
    '7. Optionally enter the walking time from your usual starting point to this stop. Set it to **0** to disable leave guidance.\n'
    '8. Choose the live polling interval. **30 seconds** is recommended.\n',
)
replace_once(
    readme,
    '- polling interval.\n',
    '- polling interval;\n- walking time to the stop.\n',
)
replace_once(
    readme,
    '| **Next bus timing** | `early`, `on_time`, `late`, or `timetable`. |\n',
    '| **Next bus timing** | `early`, `on_time`, `late`, or `timetable`. |\n'
    '| **Leave by** | Timestamp at which to start walking for the next bus when walking time is configured. |\n'
    '| **Leave in** | Minutes until the calculated leave-by time. |\n'
    '| **Leave now** | Binary sensor that turns on when it is time to start walking; intended for automations. |\n',
)

changelog = ROOT / "CHANGELOG.md"
text = changelog.read_text(encoding="utf-8")
if "## Unreleased — walking-time guidance" not in text:
    changelog.write_text(
        '# Changelog\n\n'
        '## Unreleased — walking-time guidance\n\n'
        '- Added optional per-stop walking time configuration.\n'
        '- Added Leave by and Leave in sensors derived from the already-calculated next-bus expected time.\n'
        '- Added a Leave now binary sensor for Home Assistant automations.\n'
        '- Added optional walking guidance to the generic dashboard card.\n'
        '- Walking guidance is post-processing only and does not alter the ETA/matching engine.\n\n'
        + text.removeprefix('# Changelog\n\n'),
        encoding="utf-8",
    )

# ---------------------------------------------------------------------------
# Pure tests for the walking calculation.
# ---------------------------------------------------------------------------
test = ROOT / "tests/test_walking_guidance.py"
test.write_text(
    '''"""Walking-time guidance tests."""\n\nfrom __future__ import annotations\n\nfrom datetime import datetime\nfrom zoneinfo import ZoneInfo\n\nfrom custom_components.bods_bus_tracker.walking import apply_walking_guidance\n\nTZ = ZoneInfo("Europe/London")\n\n\ndef _snapshot(expected: str = "2026-08-26T10:30:00+01:00") -> dict:\n    return {\n        "next_bus": {\n            "available": True,\n            "route": "T1",\n            "expected": expected,\n        }\n    }\n\n\ndef test_walking_guidance_disabled_at_zero() -> None:\n    now = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)\n    data = apply_walking_guidance(_snapshot(), now, 0)["next_bus"]\n    assert data["walking_minutes"] == 0\n    assert data["leave_by"] is None\n    assert data["leave_in_minutes"] is None\n    assert data["leave_now"] is False\n\n\ndef test_leave_by_and_leave_in_are_calculated() -> None:\n    now = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)\n    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]\n    assert data["leave_by"] == "2026-08-26T10:20:00+01:00"\n    assert data["leave_in_minutes"] == 20\n    assert data["leave_now"] is False\n\n\ndef test_leave_now_turns_on_after_leave_by() -> None:\n    now = datetime(2026, 8, 26, 10, 21, tzinfo=TZ)\n    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]\n    assert data["leave_in_minutes"] == 0\n    assert data["leave_now"] is True\n\n\ndef test_leave_now_turns_off_after_expected_bus_time() -> None:\n    now = datetime(2026, 8, 26, 10, 31, tzinfo=TZ)\n    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]\n    assert data["leave_by"] == "2026-08-26T10:20:00+01:00"\n    assert data["leave_in_minutes"] is None\n    assert data["leave_now"] is False\n\n\ndef test_fractional_minute_rounds_up_before_leave_time() -> None:\n    now = datetime(2026, 8, 26, 10, 19, 30, tzinfo=TZ)\n    data = apply_walking_guidance(_snapshot(), now, 10)["next_bus"]\n    assert data["leave_in_minutes"] == 1\n    assert data["leave_now"] is False\n''',
    encoding="utf-8",
)

# Remove this one-shot patch infrastructure from the feature commit.
Path(__file__).unlink()
workflow = ROOT / ".github/workflows/apply-walk-patch.yml"
if workflow.exists():
    workflow.unlink()
