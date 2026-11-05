"""Config flow Ekwateur : réponse de connexion (jetons) + choix du contrat."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EkwateurApi, EkwateurApiError, EkwateurAuthError, parse_credentials
from .const import CONF_CREDENTIALS, CONF_CUSTOMER_REF, DOMAIN

CRED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CREDENTIALS): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
        )
    }
)


class EkwateurConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._api: EkwateurApi | None = None
        self._contracts: list[dict] = []

    async def _validate(self, raw: str) -> dict[str, str]:
        # import local pour éviter un import circulaire avec __init__
        from . import build_api

        creds = parse_credentials(raw)
        if not (creds["access_token"] or creds["refresh_token"]):
            return {"base": "invalid_format"}
        self._api = build_api(self.hass, creds)
        try:
            if not creds["access_token"] and not await self._api.refresh():
                return {"base": "invalid_auth"}
            self._contracts = await self._api.get_customer_references()
        except EkwateurAuthError:
            return {"base": "invalid_auth"}
        except EkwateurApiError:
            return {"base": "cannot_connect"}
        if not self._contracts:
            return {"base": "no_contract"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(user_input[CONF_CREDENTIALS])
            if not errors:
                if len(self._contracts) == 1:
                    return await self._create(self._contracts[0]["ref"])
                return await self.async_step_contract()
        return self.async_show_form(step_id="user", data_schema=CRED_SCHEMA, errors=errors)

    async def async_step_contract(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input[CONF_CUSTOMER_REF])
        options = [{"value": c["ref"], "label": c["label"]} for c in self._contracts]
        schema = vol.Schema(
            {vol.Required(CONF_CUSTOMER_REF): SelectSelector(SelectSelectorConfig(options=options))}
        )
        return self.async_show_form(step_id="contract", data_schema=schema)

    async def _create(self, ref: str) -> ConfigFlowResult:
        await self.async_set_unique_id(ref)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Ekwateur {ref}",
            data={**self._api.as_dict(), CONF_CUSTOMER_REF: ref},
        )

    # --- Ré-authentification ---
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._validate(user_input[CONF_CREDENTIALS])
            if not errors and entry.data[CONF_CUSTOMER_REF] not in {c["ref"] for c in self._contracts}:
                errors = {"base": "wrong_account"}
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=self._api.as_dict())
        return self.async_show_form(step_id="reauth_confirm", data_schema=CRED_SCHEMA, errors=errors)
