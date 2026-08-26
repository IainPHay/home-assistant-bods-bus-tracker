"""Config flow for BODS Bus Tracker."""

from __future__ import annotations

import logging
import math
import urllib.parse
from collections.abc import Mapping
from typing import Any, override

import voluptuous as vol
from aiohttp import ClientError, ClientResponseError, ClientTimeout

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SOURCE_USER,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict

from .api import (
    StopChoice,
    StopDiscovery,
    discover_stop_services,
    is_probable_stop_code,
    parse_service_key,
    search_stops,
)
from .const import (
    AUTO_REGION,
    BODS_VEHICLE_URL,
    CONF_API_KEY,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    CONF_SERVICES,
    CONF_STOP_ATCO,
    CONF_STOP_NAME,
    CONF_STOP_SEARCH,
    CONF_STOP_SELECTION,
    CONF_WALKING_TIME,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WALKING_TIME,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MAX_WALKING_TIME,
    MIN_POLL_INTERVAL,
    MIN_WALKING_TIME,
    REGIONS,
    REGION_CENTRES,
    STOP_SEARCH_LIMIT,
    SUBENTRY_TYPE_STOP,
    VERSION,
)
from .gtfs import GTFSDownloadError, async_ensure_gtfs

_LOGGER = logging.getLogger(__name__)


async def _async_validate_api_key_generic(hass: HomeAssistant, api_key: str) -> None:
    """Validate a key without downloading a useful national vehicle feed."""
    session = async_get_clientsession(hass)
    params = {
        "operatorRef": "__bods_bus_tracker_auth_check__",
        "lineRef": "__bods_bus_tracker_auth_check__",
        "api_key": api_key,
    }
    url = f"{BODS_VEHICLE_URL}?{urllib.parse.urlencode(params)}"
    async with session.get(
        url,
        timeout=ClientTimeout(total=20),
        headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
    ) as response:
        # Authentication failure is the only client error which matters here. A
        # provider-side 400 for deliberately empty filters still proves the key was
        # accepted; 429/5xx means BODS is currently unavailable.
        if response.status in (401, 403) or response.status == 429 or response.status >= 500:
            response.raise_for_status()
        await response.read()


async def _async_validate_api_key(
    hass: HomeAssistant, api_key: str, service_key: str
) -> None:
    """Validate the BODS API key against one selected service."""
    service = parse_service_key(service_key)
    session = async_get_clientsession(hass)
    params = {
        "operatorRef": service.operator_noc,
        "lineRef": service.route,
        "api_key": api_key,
    }
    url = f"{BODS_VEHICLE_URL}?{urllib.parse.urlencode(params)}"
    async with session.get(
        url,
        timeout=ClientTimeout(total=20),
        headers={"User-Agent": f"Home-Assistant-BODS-Bus-Tracker/{VERSION}"},
    ) as response:
        response.raise_for_status()
        await response.read()


def _distance_sq(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Cheap distance proxy used only to order region attempts."""
    lon_scale = math.cos(math.radians((lat1 + lat2) / 2))
    return (lat1 - lat2) ** 2 + ((lon1 - lon2) * lon_scale) ** 2


def _region_search_order(hass: HomeAssistant) -> list[str]:
    """Order regions with the HA installation's nearest regional centre first."""
    lat = hass.config.latitude
    lon = hass.config.longitude
    if lat is None or lon is None:
        return list(REGIONS)
    return sorted(
        REGIONS,
        key=lambda region: _distance_sq(
            float(lat), float(lon), *REGION_CENTRES.get(region, (52.5, -1.5))
        ),
    )


def _region_options() -> list[SelectOptionDict]:
    return [
        SelectOptionDict(
            value=AUTO_REGION,
            label="Auto detect from exact ATCO/NaPTAN code",
        ),
        *[
            SelectOptionDict(value=slug, label=label)
            for slug, label in REGIONS.items()
        ],
    ]


def _service_options(discovery: StopDiscovery) -> list[SelectOptionDict]:
    return [
        SelectOptionDict(value=choice.key, label=choice.label)
        for choice in discovery.services
    ]


def _stop_search_schema(default_region: str = AUTO_REGION) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_REGION, default=default_region): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_region_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_STOP_SEARCH): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
        }
    )


async def _async_auto_detect_stop(
    hass: HomeAssistant, query: str
) -> tuple[str, StopChoice] | None:
    """Find an exact stop code across regional GTFS feeds."""
    query_cf = query.casefold()
    for region in _region_search_order(hass):
        try:
            path = await async_ensure_gtfs(hass, region)
            results = await hass.async_add_executor_job(
                search_stops,
                path,
                query,
                4,
                hass.config.latitude,
                hass.config.longitude,
            )
        except GTFSDownloadError:
            continue
        exact = next(
            (
                stop
                for stop in results
                if query_cf in {stop.stop_id.casefold(), stop.stop_code.casefold()}
            ),
            None,
        )
        if exact is not None:
            return region, exact
    return None


class BODSBusTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the shared BODS account config entry."""

    VERSION = 2
    MINOR_VERSION = 0

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect the BODS account once."""
        if self._async_current_entries():
            return self.async_abort(reason="account_already_configured")

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            try:
                await _async_validate_api_key_generic(self.hass, api_key)
            except ClientResponseError as exc:
                errors["base"] = (
                    "invalid_auth" if exc.status in (401, 403) else "cannot_connect"
                )
            except (ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating BODS API key")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="BODS Bus Tracker",
                    data={CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_on_create_entry(
        self, result: ConfigFlowResult
    ) -> ConfigFlowResult:
        """Immediately offer to add the first monitored stop."""
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_STOP),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported stop subentry flows."""
        return {SUBENTRY_TYPE_STOP: BODSStopSubentryFlow}

    @override
    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start BODS API-key reauthentication."""
        return await self.async_step_reauth_confirm()

    @override
    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace a rejected BODS key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = str(user_input[CONF_API_KEY]).strip()
            try:
                await _async_validate_api_key_generic(self.hass, api_key)
            except ClientResponseError as exc:
                errors["base"] = (
                    "invalid_auth" if exc.status in (401, 403) else "cannot_connect"
                )
            except (ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error reauthenticating BODS")
                errors["base"] = "unknown"
            else:
                return self.async_update_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: api_key},
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )


class BODSStopSubentryFlow(ConfigSubentryFlow):
    """Add and reconfigure monitored bus stops beneath one BODS account."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._discovery: StopDiscovery | None = None
        self._stop_results: tuple[StopChoice, ...] = ()

    async def _async_prepare_stop(
        self, region: str, stop_id: str
    ) -> SubentryFlowResult:
        """Load services for a selected stop."""
        path = await async_ensure_gtfs(self.hass, region)
        discovery = await self.hass.async_add_executor_job(
            discover_stop_services, path, stop_id
        )
        if not discovery.services:
            return self.async_show_form(
                step_id="user",
                data_schema=_stop_search_schema(region),
                errors={"base": "no_services"},
            )
        self._data[CONF_REGION] = region
        self._data[CONF_STOP_ATCO] = discovery.stop_id
        self._data[CONF_STOP_NAME] = discovery.stop_name
        self._discovery = discovery
        return await self.async_step_services()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Find the exact boarding stop."""
        errors: dict[str, str] = {}
        if user_input is not None:
            region = str(user_input[CONF_REGION])
            query = str(user_input[CONF_STOP_SEARCH]).strip()
            if not query:
                errors[CONF_STOP_SEARCH] = "stop_search_required"
            elif region == AUTO_REGION:
                if not is_probable_stop_code(query):
                    errors[CONF_STOP_SEARCH] = "auto_requires_stop_code"
                else:
                    try:
                        found = await _async_auto_detect_stop(self.hass, query)
                    except Exception:
                        _LOGGGER.exception("Unexpected error auto-detecting BODS region")
                        errors["base"] = "unknown"
                    else:
                        if found is None:
                            errors[CONF_STOP_SEARCH] = "stop_not_found_all_regions"
                        else:
                            found_region, stop = found
                            try:
                                return await self._async_prepare_stop(
                                    found_region, stop.stop_id
                                )
                            except GTFSDownloadError:
                                errors["base"] = "gtfs_download_failed"
                            except Exception:
                                _LOGGGER.exception(
                                    "Unexpected error discovering BODS stop services"
                                )
                                errors["base"] = "unknown"
            else:
                try:
                    path = await async_ensure_gtfs(self.hass, region)
                    results = await self.hass.async_add_executor_job(
                        search_stops,
                        path,
                        query,
                        STOP_SEARCH_LIMIT,
                        self.hass.config.latitude,
                        self.hass.config.longitude,
                    )
                except GTFSDownloadError:
                    errors["base"] = "gtfs_download_failed"
                except Exception:
                    _LOGGGER.exception("Unexpected error searching BODS stops")
                    errors["base"] = "unknown"
                else:
                    if not results:
                        errors[CONF_STOP_SEARCH] = "stop_search_no_results"
                    elif len(results) == 1:
                        try:
                            return await self._async_prepare_stop(
                                region, results[0].stop_id
                            )
                        except Exception:
                            _LOGGGER.exception(
                                "Unexpected error discovering BODS stop services"
                            )
                            errors["base"] = "unknown"
                    else:
                        self._data[CONF_REGION] = region
                        self._stop_results = results
                        return await self.async_step_stop_select()

        return self.async_show_form(
            step_id="user",
            data_schema=_stop_search_schema(),
            errors=errors,
        )

    @override
    async def async_step_stop_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose between matching boarding points."""
        errors: dict[str, str] = {}
        if user_input is not None:
            stop_id = str(user_input[CONF_STOP_SELECTION])
            if not any(stop.stop_id == stop_id for stop in self._stop_results):
                errors[CONF_STOP_SELECTION] = "stop_selection_invalid"
            else:
                try:
                    return await self._async_prepare_stop(
                        self._data[CONF_REGION], stop_id
                    )
                except GTFSDownloadError:
                    errors["base"] = "gtfs_download_failed"
                except Exception:
                    _LOGGER.exception("Unexpected error selecting BODS stop")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="stop_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_SELECTION): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=stop.stop_id, label=stop.label)
                                for stop in self._stop_results
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_services(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose routes for the new stop."""
        assert self._discovery is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = list(user_input[CONF_SERVICES])
            if not selected:
                errors[CONF_SERVICES] = "select_service"
            else:
                entry = self._get_entry()
                try:
                    await _async_validate_api_key(
                        self.hass, entry.data[CONF_API_KEY], selected[0]
                    )
                except ClientResponseError as exc:
                    errors["base"] = (
                        "invalid_auth"
                        if exc.status in (401, 403)
                        else "cannot_connect"
                    )
                except (ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGGER.exception("Unexpected error validating selected BODS service")
                    errors["base"] = "unknown"
                else:
                    unique_id = f"{self._data[CONF_REGION]}:{self._data[CONF_STOP_ATCO]}"
                    if any(
                        subentry.unique_id == unique_id
                        for subentry in entry.subentries.values()
                    ):
                        return self.async_abort(reason="already_configured")
                    self._data[CONF_SERVICES] = selected
                    self._data[CONF_WALKING_TIME] = int(
                        user_input.get(CONF_WALKING_TIME, DEFAULT_WALKING_TIME)
                    )
                    self._data[CONF_POLL_INTERVAL] = int(
                        user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                    )
                    return self.async_create_entry(
                        title=(
                            f"{self._discovery.stop_name} "
                            f"({self._discovery.stop_id})"
                        ),
                        data=self._data,
                        unique_id=unique_id,
                    )

        return self.async_show_form(
            step_id="services",
            description_placeholders={
                "stop_name": self._discovery.stop_name,
                "stop_atco": self._discovery.stop_id,
                "region": REGIONS.get(
                    self._data[CONF_REGION], self._data[CONF_REGION]
                ),
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_service_options(self._discovery),
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    ),
                    vol.Optional(
                        CONF_WALKING_TIME, default=DEFAULT_WALKING_TIME
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_WALKING_TIME,
                            max=MAX_WALKING_TIME,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_POLL_INTERVAL,
                            max=MAX_POLL_INTERVAL,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change services, walking time and poll interval for one stop."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        try:
            path = await async_ensure_gtfs(self.hass, subentry.data[CONF_REGION])
            discovery = await self.hass.async_add_executor_job(
                discover_stop_services, path, subentry.data[CONF_STOP_ATCO]
            )
        except GTFSDownloadError:
            return self.async_abort(reason="gtfs_download_failed")
        except Exception:
            _LOGGER.exception("Unable to prepare BODS stop reconfigure flow")
            return self.async_abort(reason="unknown")

        if user_input is not None:
            selected = list(user_input[CONF_SERVICES])
            if not selected:
                errors[CONF_SERVICES] = "select_service"
            else:
                try:
                    await _async_validate_api_key(
                        self.hass, entry.data[CONF_API_KEY], selected[0]
                    )
                except ClientResponseError as exc:
                    errors["base"] = (
                        "invalid_auth"
                        if exc.status in (401, 403)
                        else "cannot_connect"
                    )
                except (ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating BODS service")
                    errors["base"] = "unknown"
                else:
                    return self.async_update_and_abort(
                        entry,
                        subentry,
                        data_updates={
                            CONF_SERVICES: selected,
                            CONF_WALKING_TIME: int(user_input[CONF_WALKING_TIME]),
                            CONF_POLL_INTERVAL: int(user_input[CONF_POLL_INTERVAL]),
                        },
                    )

        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "stop_name": subentry.data[CONF_STOP_NAME],
                "stop_atco": subentry.data[CONF_STOP_ATCO],
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERVICES,
                        default=list(subentry.data[CONF_SERVICES]),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_service_options(discovery),
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    ),
                    vol.Required(
                        CONF_WALKING_TIME,
                        default=int(
                            subentry.data.get(
                                CONF_WALKING_TIME, DEFAULT_WALKING_TIME
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_WALKING_TIME,
                            max=MAX_WALKING_TIME,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=int(
                            subentry.data.get(
                                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_POLL_INTERVAL,
                            max=MAX_POLL_INTERVAL,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                }
            ),
            errors=errors,
        )
