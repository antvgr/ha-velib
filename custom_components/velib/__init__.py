"""The Vélib' Métropole integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import aiohttp

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.loader import async_get_integration

from .api import VelibAccountClient, VelibPublicClient
from .const import (
    CONF_ENTRY_TYPE,
    CONF_SCAN_INTERVAL,
    CONF_STATIONS,
    DEFAULT_STATIONS_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_ACCOUNT,
)
from .coordinator import VelibAccountCoordinator, VelibStationsCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CARD_FILENAME = "velib-station-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
CARD_PATH = str(Path(__file__).parent / "www" / CARD_FILENAME)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and auto-load it on the frontend.

    Runs once per Home Assistant start; no manual Lovelace resource needed.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("card_registered"):
        return
    data["card_registered"] = True

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, CARD_PATH, False)]
    )

    version = ""
    try:
        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "")
    except Exception:  # noqa: BLE001 - version only used to bust the cache
        version = ""
    add_extra_js_url(hass, f"{CARD_URL}?v={version}" if version else CARD_URL)


@dataclass
class VelibRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: VelibStationsCoordinator | VelibAccountCoordinator


type VelibConfigEntry = ConfigEntry[VelibRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: VelibConfigEntry) -> bool:
    """Set up a Vélib' config entry (stations or account)."""
    await _async_register_card(hass)

    public = VelibPublicClient(async_get_clientsession(hass))

    coordinator: VelibStationsCoordinator | VelibAccountCoordinator
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ACCOUNT:
        # Dedicated session: authentication relies on cookies.
        session = async_create_clientsession(
            hass, cookie_jar=aiohttp.CookieJar()
        )
        client = VelibAccountClient(
            session, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
        coordinator = VelibAccountCoordinator(hass, entry, client, public)
    else:
        options = {**entry.data, **entry.options}
        coordinator = VelibStationsCoordinator(
            hass,
            entry,
            public,
            list(options.get(CONF_STATIONS, [])),
            int(options.get(CONF_SCAN_INTERVAL, DEFAULT_STATIONS_INTERVAL)),
        )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = VelibRuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: VelibConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VelibConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
