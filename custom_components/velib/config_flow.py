"""Config flow for Vélib' Métropole."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
import unicodedata

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.location import distance

from .api import (
    Station,
    VelibAccountClient,
    VelibAuthError,
    VelibError,
    VelibPublicClient,
)
from .const import (
    CONF_ENTRY_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_SEARCH,
    CONF_STATIONS,
    DEFAULT_STATIONS_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_ACCOUNT,
    ENTRY_TYPE_STATIONS,
    MIN_STATIONS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

MAX_CHOICES = 60


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _station_options(
    hass: HomeAssistant,
    stations: dict[str, Station],
    query: str | None,
    selected: list[str],
) -> list[SelectOptionDict]:
    """Build the station choices: current selection + search matches (or nearest)."""
    home = (hass.config.latitude, hass.config.longitude)

    def dist_km(s: Station) -> float | None:
        if s.latitude is None or s.longitude is None:
            return None
        meters = distance(home[0], home[1], s.latitude, s.longitude)
        return meters / 1000 if meters is not None else None

    def label(s: Station) -> str:
        d = dist_km(s)
        suffix = f" — {d:.1f} km" if d is not None else ""
        return f"{s.name} ({s.code}){suffix}"

    candidates = list(stations.values())
    if query:
        q = _normalize(query.strip())
        candidates = [s for s in candidates if q in _normalize(s.name) or q == s.code]
    candidates.sort(key=lambda s: (dist_km(s) is None, dist_km(s) or 0))

    codes: list[str] = [c for c in selected if c in stations]
    for s in candidates:
        if len(codes) >= MAX_CHOICES + len(selected):
            break
        if s.code not in codes:
            codes.append(s.code)
    return [SelectOptionDict(value=c, label=label(stations[c])) for c in codes]


def _search_schema(default: str = "") -> vol.Schema:
    return vol.Schema({vol.Optional(CONF_SEARCH, default=default): TextSelector()})


def _select_schema(
    options: list[SelectOptionDict], selected: list[str], interval: int
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_STATIONS, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=options, multiple=True, mode=SelectSelectorMode.LIST
                )
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=interval): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_STATIONS_INTERVAL,
                    max=3600,
                    step=30,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)
ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)


async def _validate_account(hass: HomeAssistant, username: str, password: str) -> None:
    session = async_create_clientsession(
        hass, cookie_jar=aiohttp.CookieJar()
    )
    try:
        client = VelibAccountClient(session, username, password)
        await client.async_login()
        await client.async_get_all_infos_user()
    finally:
        await session.close()


class VelibConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vélib' Métropole."""

    VERSION = 1

    def __init__(self) -> None:
        self._stations: dict[str, Station] = {}
        self._query: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what to set up."""
        return self.async_show_menu(step_id="user", menu_options=["stations", "account"])

    # ----------------------------------------------------------------- stations

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search stations (by name or code); empty search = nearest to home."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._query = user_input.get(CONF_SEARCH, "")
            return await self.async_step_select_stations()
        if not self._stations:
            try:
                self._stations = await VelibPublicClient(
                    async_get_clientsession(self.hass)
                ).async_get_stations()
            except VelibError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="stations", data_schema=_search_schema(self._query), errors=errors
        )

    async def async_step_select_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the stations to follow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_STATIONS]:
                errors[CONF_STATIONS] = "no_station"
            else:
                await self.async_set_unique_id(ENTRY_TYPE_STATIONS)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Stations Vélib'",
                    data={CONF_ENTRY_TYPE: ENTRY_TYPE_STATIONS},
                    options={
                        CONF_STATIONS: user_input[CONF_STATIONS],
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )
        options = _station_options(self.hass, self._stations, self._query, [])
        if not options:
            return self.async_show_form(
                step_id="stations",
                data_schema=_search_schema(self._query),
                errors={CONF_SEARCH: "no_match"},
            )
        return self.async_show_form(
            step_id="select_stations",
            data_schema=_select_schema(options, [], DEFAULT_STATIONS_INTERVAL),
            errors=errors,
        )

    # ------------------------------------------------------------------ account

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in with a Vélib' account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(f"{ENTRY_TYPE_ACCOUNT}_{username.casefold()}")
            self._abort_if_unique_id_configured()
            errors = await self._try_login(username, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_ACCOUNT,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="account",
            data_schema=self.add_suggested_values_to_schema(ACCOUNT_SCHEMA, user_input),
            errors=errors,
        )

    async def _try_login(self, username: str, password: str) -> dict[str, str]:
        try:
            await _validate_account(self.hass, username, password)
        except VelibAuthError:
            return {"base": "invalid_auth"}
        except VelibError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while logging in")
            return {"base": "unknown"}
        return {}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._try_login(
                entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    # ------------------------------------------------------------------ options

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options are only available for the stations entry."""
        return VelibOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        return config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_STATIONS


class VelibOptionsFlow(OptionsFlow):
    """Change the followed stations and the refresh interval."""

    def __init__(self) -> None:
        self._stations: dict[str, Station] = {}
        self._query = ""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._query = user_input.get(CONF_SEARCH, "")
            return await self.async_step_select_stations()
        try:
            self._stations = await VelibPublicClient(
                async_get_clientsession(self.hass)
            ).async_get_stations()
        except VelibError:
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="init", data_schema=_search_schema(), errors=errors
        )

    async def async_step_select_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        selected: list[str] = list(current.get(CONF_STATIONS, []))
        interval = int(current.get(CONF_SCAN_INTERVAL, DEFAULT_STATIONS_INTERVAL))
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_STATIONS]:
                errors[CONF_STATIONS] = "no_station"
            else:
                return self.async_create_entry(
                    data={
                        CONF_STATIONS: user_input[CONF_STATIONS],
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    }
                )
        options = _station_options(self.hass, self._stations, self._query, selected)
        return self.async_show_form(
            step_id="select_stations",
            data_schema=_select_schema(options, selected, interval),
            errors=errors,
        )
