"""Client pour l'API de l'espace client Ekwateur (api-ec.ekwateur.fr).

Authentification :
- l'utilisateur se connecte lui-même sur le site (captcha résolu par un humain) ;
- la réponse de POST /auth contient AccessToken (24 h) + RefreshToken (Cognito) ;
- l'intégration renouvelle l'AccessToken avec le RefreshToken, d'abord via
  l'endpoint Ekwateur /refresh_token, sinon via le flux standard Cognito
  REFRESH_TOKEN_AUTH du même client applicatif.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    EP_BILLS_HISTORY,
    EP_METERS_READINGS,
    EP_REFRESH,
    EP_TARIFF_OPTIONS,
    EP_USER_INFO,
    WEB_ORIGIN,
)

_LOGGER = logging.getLogger(__name__)


class EkwateurAuthError(Exception):
    """Jeton absent, invalide ou expiré (HTTP 401/403)."""


class EkwateurApiError(Exception):
    """Erreur réseau ou réponse inattendue."""


# --------------------------------------------------------------------------- #
# Utilitaires jetons
# --------------------------------------------------------------------------- #
def _jwt_claims(token: str | None) -> dict:
    """Claims d'un JWT (sans vérification de signature, usage local uniquement)."""
    try:
        payload = token.split(".")[1]  # type: ignore[union-attr]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (AttributeError, IndexError, ValueError, TypeError):
        return {}


def token_expiry(token: str | None) -> datetime | None:
    exp = _jwt_claims(token).get("exp")
    return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None


def parse_credentials(value: str) -> dict:
    """Accepte : JSON de la réponse /auth, JSON de la clé localStorage 'auth',
    un RefreshToken seul (JWE, 5 segments) ou un AccessToken seul (JWT, 3 segments).

    Retourne {"access_token", "refresh_token", "username"} (valeurs possiblement None).
    """
    value = (value or "").strip()
    out: dict[str, str | None] = {"access_token": None, "refresh_token": None, "username": None}
    if value.startswith("{"):
        try:
            data = json.loads(value)
        except ValueError:
            data = {}
        out["access_token"] = data.get("AccessToken") or data.get("accessToken")
        out["refresh_token"] = data.get("RefreshToken") or data.get("refreshToken")
        out["username"] = data.get("Username") or data.get("username")
    else:
        token = value.removeprefix("Bearer ").strip().strip('"')
        if token.count(".") == 4:
            out["refresh_token"] = token
        elif token.count(".") == 2:
            out["access_token"] = token
    if out["access_token"] and not out["username"]:
        out["username"] = _jwt_claims(out["access_token"]).get("username")
    return out


def _extract_access_token(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("AccessToken", "accessToken", "access_token", "token"):
        val = data.get(key)
        if isinstance(val, str) and val.count(".") == 2:
            return val
    for key in ("data", "auth", "AuthenticationResult"):
        found = _extract_access_token(data.get(key))
        if found:
            return found
    return None


def _extract_refresh_token(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("RefreshToken", "refreshToken", "refresh_token"):
        if isinstance(data.get(key), str):
            return data[key]
    for key in ("data", "AuthenticationResult"):
        found = _extract_refresh_token(data.get(key))
        if found:
            return found
    return None


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class EkwateurApi:
    """Accès en lecture seule aux données du compte."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str | None,
        refresh_token: str | None = None,
        username: str | None = None,
        cognito_client_id: str | None = None,
        cognito_region: str | None = None,
    ) -> None:
        self._session = session
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.username = username
        claims = _jwt_claims(access_token)
        self.cognito_client_id = cognito_client_id or claims.get("client_id")
        iss = claims.get("iss", "")
        self.cognito_region = cognito_region or (
            iss.split("cognito-idp.")[1].split(".")[0] if "cognito-idp." in iss else None
        )

    # ----- état ------------------------------------------------------------ #
    @property
    def expires_at(self) -> datetime | None:
        return token_expiry(self.access_token)

    def as_dict(self) -> dict:
        """Ce qu'il faut persister dans l'entrée de configuration."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "username": self.username,
            "cognito_client_id": self.cognito_client_id,
            "cognito_region": self.cognito_region,
        }

    # ----- renouvellement --------------------------------------------------- #
    async def refresh(self) -> bool:
        """Obtient un nouvel AccessToken. True si succès."""
        if not self.refresh_token:
            return False
        if await self._refresh_via_ekwateur():
            return True
        if await self._refresh_via_cognito():
            return True
        return False

    async def _refresh_via_ekwateur(self) -> bool:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": WEB_ORIGIN,
            "Referer": f"{WEB_ORIGIN}/",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        # Le format exact du corps n'est pas documenté : on essaie les variantes usuelles.
        bodies = [
            {"refreshToken": self.refresh_token, "username": self.username, "source": "customer_portal"},
            {"RefreshToken": self.refresh_token, "Username": self.username},
            {"refresh_token": self.refresh_token, "username": self.username},
            {"refreshToken": self.refresh_token, "login": self.username, "source": "customer_portal"},
        ]
        for body in bodies:
            body = {k: v for k, v in body.items() if v is not None}
            try:
                async with asyncio.timeout(30):
                    resp = await self._session.post(
                        f"{API_BASE}{EP_REFRESH}", headers=headers, json=body
                    )
                    status = resp.status
                    data = await resp.json(content_type=None) if status < 400 else None
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Ekwateur /refresh_token erreur: %s", err)
                return False
            if status >= 400:
                _LOGGER.debug("Ekwateur /refresh_token clés=%s -> HTTP %s", list(body), status)
                continue
            if self._apply(data):
                _LOGGER.info("Jeton renouvelé via Ekwateur (clés %s)", list(body))
                return True
        return False

    async def _refresh_via_cognito(self) -> bool:
        if not (self.cognito_client_id and self.cognito_region):
            return False
        url = f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
        }
        body = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "ClientId": self.cognito_client_id,
            "AuthParameters": {"REFRESH_TOKEN": self.refresh_token},
        }
        try:
            async with asyncio.timeout(30):
                resp = await self._session.post(url, headers=headers, data=json.dumps(body))
                data = await resp.json(content_type=None)
                status = resp.status
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Cognito refresh erreur: %s", err)
            return False
        if status >= 400:
            # ex. NotAuthorizedException (refresh expiré/révoqué) ou client avec secret
            _LOGGER.warning(
                "Renouvellement Cognito refusé: %s %s",
                (data or {}).get("__type"),
                (data or {}).get("message"),
            )
            return False
        if self._apply(data):
            _LOGGER.info("Jeton renouvelé via Cognito")
            return True
        return False

    def _apply(self, data: Any) -> bool:
        new_access = _extract_access_token(data)
        if not new_access:
            return False
        self.access_token = new_access
        new_refresh = _extract_refresh_token(data)
        if new_refresh:  # rotation éventuelle
            self.refresh_token = new_refresh
        self.username = self.username or _jwt_claims(new_access).get("username")
        return True

    # ----- requêtes --------------------------------------------------------- #
    async def _get(self, path: str, _retry: bool = True) -> Any:
        if not self.access_token:
            if not await self.refresh():
                raise EkwateurAuthError("Aucun jeton valide")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Origin": WEB_ORIGIN,
            "Referer": f"{WEB_ORIGIN}/",
        }
        try:
            async with asyncio.timeout(30):
                resp = await self._session.get(f"{API_BASE}{path}", headers=headers)
                status = resp.status
                data = await resp.json(content_type=None) if status < 400 else None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise EkwateurApiError(f"Erreur réseau sur {path}: {err}") from err
        except ValueError as err:
            raise EkwateurApiError(f"Réponse non JSON sur {path}") from err

        if status in (401, 403):
            if _retry and await self.refresh():
                return await self._get(path, _retry=False)
            raise EkwateurAuthError(f"HTTP {status} sur {path}")
        if status >= 400:
            raise EkwateurApiError(f"HTTP {status} sur {path}")
        return data

    async def get_user_information(self) -> dict:
        return await self._get(EP_USER_INFO)

    async def get_meters_readings(self, ref: str) -> Any:
        return await self._get(EP_METERS_READINGS.format(ref=ref))

    async def get_bills_history(self, ref: str) -> dict:
        return await self._get(EP_BILLS_HISTORY.format(ref=ref))

    async def get_tariff_options(self, ref: str) -> dict:
        return await self._get(EP_TARIFF_OPTIONS.format(ref=ref))

    async def get_customer_references(self) -> list[dict]:
        """Liste des contrats (customerReference + adresse) du compte."""
        info = await self.get_user_information()
        out = []
        for c in (info or {}).get("contracts") or []:
            ref = c.get("customerReference")
            if not ref:
                continue
            addr = c.get("address") or {}
            label = " ".join(
                str(x)
                for x in (addr.get("streetNumber"), addr.get("street"), addr.get("zipCode"), addr.get("municipality"))
                if x
            )
            out.append({"ref": ref, "label": f"{ref} – {label}".strip(" –")})
        return out
