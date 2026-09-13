"""Home Assistant-native config-flow tests for BODS Bus Tracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bods_bus_tracker.const import CONF_API_KEY, DOMAIN


def _http_error(status: int) -> ClientResponseError:
    """Build the minimal aiohttp response error needed by the flow."""
    return ClientResponseError(None, (), status=status)


async def test_user_form(hass) -> None:
    """The integration starts with a UI-only API-key form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_success(hass) -> None:
    """A valid API key creates the single BODS account entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with (
        patch(
            "custom_components.bods_bus_tracker.config_flow._async_validate_api_key_generic",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.bods_bus_tracker.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "valid-key"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "BODS Bus Tracker"
    assert result2["data"] == {CONF_API_KEY: "valid-key"}


async def test_duplicate_account_aborts(hass) -> None:
    """Only one shared BODS account config entry is allowed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "existing-key"},
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_http_error(401), "invalid_auth"),
        (_http_error(403), "access_forbidden"),
        (_http_error(429), "rate_limited"),
        (_http_error(500), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_errors(hass, error: Exception, expected: str) -> None:
    """Config flow reports actionable BODS connection failures."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key_generic",
        new=AsyncMock(side_effect=error),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": expected}


async def test_reauth_success(hass) -> None:
    """A successful reauth updates the shared API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "old-key"},
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key_generic",
        new=AsyncMock(return_value=None),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new-key"},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "invalid_auth"),
        (403, "access_forbidden"),
        (429, "rate_limited"),
    ],
)
async def test_reauth_http_errors(hass, status: int, expected: str) -> None:
    """Reauth keeps authentication, access and throttling errors distinct."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="BODS Bus Tracker",
        data={CONF_API_KEY: "old-key"},
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    with patch(
        "custom_components.bods_bus_tracker.config_flow._async_validate_api_key_generic",
        new=AsyncMock(side_effect=_http_error(status)),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "replacement-key"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": expected}
