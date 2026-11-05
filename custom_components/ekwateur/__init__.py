"""Intégration Ekwateur pour Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EkwateurApi
from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, CONF_USERNAME
from .coordinator import EkwateurCoordinator

PLATFORMS = [Platform.SENSOR]

type EkwateurConfigEntry = ConfigEntry[EkwateurCoordinator]


def build_api(hass: HomeAssistant, data: dict) -> EkwateurApi:
    return EkwateurApi(
        async_get_clientsession(hass),
        access_token=data.get(CONF_ACCESS_TOKEN),
        refresh_token=data.get(CONF_REFRESH_TOKEN),
        username=data.get(CONF_USERNAME),
    )


async def async_setup_entry(hass: HomeAssistant, entry: EkwateurConfigEntry) -> bool:
    coordinator = EkwateurCoordinator(hass, entry, build_api(hass, dict(entry.data)))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EkwateurConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
