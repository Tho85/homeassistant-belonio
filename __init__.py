"""The Belonio integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import(
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .belonio import Belonio

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Belonio from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = Belonio(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
