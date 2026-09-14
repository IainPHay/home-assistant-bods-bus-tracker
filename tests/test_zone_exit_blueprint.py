"""Policy checks for the zone-exit catchable-bus blueprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

BLUEPRINT_PATH = Path(
    "blueprints/automation/bods_bus_tracker_zone_exit_catchable.yaml"
)


class _BlueprintLoader(yaml.SafeLoader):
    """Minimal YAML loader that preserves Home Assistant !input tags."""


def _input_constructor(
    loader: _BlueprintLoader, node: yaml.nodes.ScalarNode
) -> dict[str, str]:
    return {"__input__": loader.construct_scalar(node)}


_BlueprintLoader.add_constructor("!input", _input_constructor)


def _load_blueprint() -> dict[str, Any]:
    content = BLUEPRINT_PATH.read_text(encoding="utf-8")
    loaded = yaml.load(content, Loader=_BlueprintLoader)
    assert isinstance(loaded, dict)
    return loaded


def _section_inputs(blueprint: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    raw_inputs = blueprint["blueprint"]["input"]
    for value in raw_inputs.values():
        if isinstance(value, dict) and isinstance(value.get("input"), dict):
            result.update(value["input"])
    return result


def _render_condition(
    condition: str,
    *,
    catchable_status: str | None,
    departure: dict[str, Any],
    sensor_state: str,
) -> str:
    """Render the blueprint condition with representative Home Assistant state."""
    environment = Environment(undefined=StrictUndefined, autoescape=False)
    environment.globals["states"] = lambda _entity_id: sensor_state
    return environment.from_string(condition).render(
        catchable_status=catchable_status,
        catchable_entity="sensor.test_catchable",
        departure=departure,
    ).strip()


def test_zone_exit_condition_renders_explicit_boolean() -> None:
    """A valid catchable departure must render boolean true, never a timestamp."""
    data = _load_blueprint()
    condition = data["conditions"][0]["value_template"]
    departure = {
        "route": "X18",
        "expected": "2026-09-14T17:18:00+01:00",
        "scheduled": "2026-09-14T17:18:00+01:00",
    }

    assert _render_condition(
        condition,
        catchable_status="ok",
        departure=departure,
        sensor_state="X18",
    ) == "True"
    assert _render_condition(
        condition,
        catchable_status="no_departures",
        departure=departure,
        sensor_state="X18",
    ) == "False"
    assert _render_condition(
        condition,
        catchable_status="ok",
        departure={},
        sensor_state="unknown",
    ) == "False"


def test_zone_exit_blueprint_uses_trusted_catchable_state() -> None:
    """The blueprint must consume Catchable bus rather than recalculate it."""
    data = _load_blueprint()
    content = BLUEPRINT_PATH.read_text(encoding="utf-8")
    inputs = _section_inputs(data)

    assert data["blueprint"]["domain"] == "automation"
    assert data["blueprint"]["homeassistant"]["min_version"] == "2026.8.0"

    assert {
        "traveller",
        "origin_zone",
        "catchable_bus_entity",
        "notification_title",
        "primary_notification_action",
        "secondary_notification_action",
    } <= inputs.keys()

    catchable_filter = inputs["catchable_bus_entity"]["selector"]["entity"]["filter"]
    assert {
        "domain": "sensor",
        "integration": "bods_bus_tracker",
    } in catchable_filter

    trigger = data["triggers"][0]
    assert trigger["trigger"] == "zone"
    assert trigger["event"] == "leave"
    assert trigger["entity_id"] == {"__input__": "traveller"}
    assert trigger["zone"] == {"__input__": "origin_zone"}

    condition = data["conditions"][0]["value_template"]
    assert "catchable_status == 'ok'" in condition
    assert "departure.get('route', '')" in condition

    # The trusted entity provides both selected journeys and lead-time policy.
    assert "state_attr(catchable_entity, 'departure')" in content
    assert "state_attr(catchable_entity, 'following_departure')" in content
    assert "state_attr(catchable_entity, 'walking_minutes')" in content
    assert "state_attr(catchable_entity, 'margin_minutes')" in content
    assert "state_attr(catchable_entity, 'required_lead_minutes')" in content

    # Do not regress into recreating catchability from raw departure lists/time math.
    assert "_departures_for_guidance" not in content
    assert "departures" not in data["variables"]
    assert "now()" not in content
    assert "timedelta" not in content

    # Both notification hooks must receive variables prepared by the blueprint.
    assert data["actions"][1]["sequence"] == {
        "__input__": "primary_notification_action"
    }
    assert data["actions"][2]["sequence"] == {
        "__input__": "secondary_notification_action"
    }
