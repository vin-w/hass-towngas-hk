"""Config flow for Hong Kong Towngas."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    ACCOUNT_API,
    CONF_ACCOUNT_NO,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGIN_API,
    LOGIN_PAGE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


def _extract_csrf_token(html: str) -> str | None:
    """Extract CSRF token from login page HTML."""
    for meta_name in ("csrf-token", "RequestVerificationToken", "_csrf"):
        match = re.search(
            rf'<meta[^>]+name=["\']{re.escape(meta_name)}["\'][^>]+content=["\'](CfDJ8[^"\']+)',
            html,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
        match = re.search(
            rf'<meta[^>]+content=["\'](CfDJ8[^"\']+)["\'][^>]+name=["\']{re.escape(meta_name)}',
            html,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)
    match = re.search(r'["\' ](CfDJ8[A-Za-z0-9_\-]{60,})["\']', html)
    return match.group(1) if match else None


async def _do_login(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> str:
    """Login and return post-login csrfToken; raises ValueError on failure."""
    async with session.get(
        LOGIN_PAGE,
        headers={
            "user-agent": USER_AGENT,
            "accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
    ) as resp:
        resp.raise_for_status()
        html = await resp.text()

    csrf_token = _extract_csrf_token(html)
    if not csrf_token:
        raise ValueError("cannot_get_token")

    async with session.post(
        LOGIN_API,
        headers={
            "user-agent": USER_AGENT,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://eservice.towngas.com",
            "referer": LOGIN_PAGE,
            "requestverificationtoken": csrf_token,
        },
        data={
            "LoginID": username,
            "UserName": username,
            "password": password,
            "Password": password,
            "Language": "en",
        },
        timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)

    if not body.get("email"):
        raise ValueError("invalid_auth")

    return body.get("csrfToken", csrf_token)


async def _get_accounts(
    session: aiohttp.ClientSession,
    csrf_token: str,
) -> list[str]:
    """Return list of account numbers for logged-in user."""
    async with session.post(
        ACCOUNT_API,
        headers={
            "user-agent": USER_AGENT,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "x-requested-with": "XMLHttpRequest",
            "requestverificationtoken": csrf_token,
        },
        timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
    ) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


class TownGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hong Kong Towngas."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._csrf_token: str = ""
        self._accounts: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: collect username + password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_create_clientsession(self.hass)

            try:
                self._csrf_token = await _do_login(
                    session,
                    user_input[CONF_USERNAME].strip(),
                    user_input[CONF_PASSWORD],
                )
                self._accounts = await _get_accounts(session, self._csrf_token)
                self._username = user_input[CONF_USERNAME].strip()
                self._password = user_input[CONF_PASSWORD]
            except ValueError as err:
                errors["base"] = str(err)
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Towngas login")
                errors["base"] = "unknown"

            if not errors:
                if len(self._accounts) == 1:
                    return self._create_entry(self._accounts[0])
                return await self.async_step_account()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: choose account number (only if multiple accounts exist)."""
        if user_input is not None:
            return self._create_entry(user_input[CONF_ACCOUNT_NO])

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_NO): vol.In(self._accounts)}),
        )

    def _create_entry(self, account_no: str) -> FlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"Towngas {account_no}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_ACCOUNT_NO: account_no,
            },
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-authenticate when credentials expire."""
        return await self.async_step_user(user_input)
