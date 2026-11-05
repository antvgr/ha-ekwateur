import asyncio
import base64
import json
import time

import pytest

from ekw.api import EkwateurApi, EkwateurAuthError, parse_credentials


def _b(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def _jwt(exp):
    return _b({"alg": "none"}) + "." + _b({
        "exp": exp, "username": "EKW1", "client_id": "cid",
        "iss": "https://cognito-idp.eu-west-1.amazonaws.com/pool"}) + ".sig"


RT = "a.b.c.d.e"
OLD, NEW = _jwt(int(time.time()) - 10), _jwt(int(time.time()) + 86400)


class _Resp:
    def __init__(self, status, data):
        self.status, self._d = status, data

    async def json(self, content_type=None):
        return self._d


class _Session:
    """/refresh_token accepte refreshToken+username ; l'API exige le nouveau jeton."""

    def __init__(self):
        self.calls = []

    async def post(self, url, headers=None, json=None, data=None):
        self.calls.append(url)
        if "refresh_token" in url:
            ok = json.get("refreshToken") == RT and json.get("username") == "EKW1"
            return _Resp(200, {"AccessToken": NEW}) if ok else _Resp(400, None)
        raise AssertionError(url)

    async def get(self, url, headers=None):
        if headers["Authorization"] == f"Bearer {NEW}":
            return _Resp(200, {"contracts": [{"customerReference": "EKW1", "address": {}}]})
        return _Resp(401, None)


def test_parse_credentials():
    c = parse_credentials(json.dumps({"AccessToken": OLD, "RefreshToken": RT, "Username": "EKW1"}))
    assert c == {"access_token": OLD, "refresh_token": RT, "username": "EKW1"}
    assert parse_credentials(RT)["refresh_token"] == RT
    assert parse_credentials("Bearer " + OLD)["access_token"] == OLD


def test_retry_after_401_refreshes_token():
    api = EkwateurApi(_Session(), OLD, RT, "EKW1")
    refs = asyncio.run(api.get_customer_references())
    assert refs[0]["ref"] == "EKW1" and api.access_token == NEW


def test_refresh_needs_username():
    assert not asyncio.run(EkwateurApi(_Session(), OLD, RT, None).refresh())


def test_no_refresh_token_raises():
    with pytest.raises(EkwateurAuthError):
        asyncio.run(EkwateurApi(_Session(), OLD, None).get_customer_references())
