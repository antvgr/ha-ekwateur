"""Coordinateur de mise à jour Ekwateur."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EkwateurApi, EkwateurApiError, EkwateurAuthError
from .const import CONF_CUSTOMER_REF, DEFAULT_SCAN_INTERVAL, DOMAIN, REFRESH_MARGIN
from .parser import parse_bills, parse_meter_readings, parse_tariff

_LOGGER = logging.getLogger(__name__)


class EkwateurCoordinator(DataUpdateCoordinator[dict]):
    """Récupère relèves, échéancier et grille tarifaire."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: EkwateurApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.api = api
        self.ref: str = entry.data[CONF_CUSTOMER_REF]

    def _persist_tokens(self) -> None:
        """Sauvegarde les jetons s'ils ont changé (renouvellement / rotation)."""
        new = self.api.as_dict()
        old = self.config_entry.data
        if any(old.get(k) != v for k, v in new.items()):
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**old, **new}
            )

    async def _async_update_data(self) -> dict:
        exp = self.api.expires_at
        if exp is None or exp - dt_util.utcnow() < REFRESH_MARGIN:
            if not await self.api.refresh() and (exp is None or exp <= dt_util.utcnow()):
                raise ConfigEntryAuthFailed("Session Ekwateur expirée, reconnexion nécessaire")
        try:
            readings = await self.api.get_meters_readings(self.ref)
            bills = await self.api.get_bills_history(self.ref)
            tariff = await self.api.get_tariff_options(self.ref)
        except EkwateurAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EkwateurApiError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            self._persist_tokens()

        return {
            "meter": parse_meter_readings(readings),
            "bills": parse_bills(bills),
            "tariff": parse_tariff(tariff),
            "token_expires": self.api.expires_at,
        }
