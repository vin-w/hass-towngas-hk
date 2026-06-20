"""Config flow for Hong Kong Towngas."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ACCOUNT_API,
    CONF_ACCOUNT_NO,
    DEFAULT_TIMEOUT,
    DOMAIN,
    GENERATE_OTP_API,
    LOGIN_API,
    LOGIN_PAGE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

from .coordinator import extract_csrf_token as _extract_csrf_token  # noqa: E402

_TIMEOUT = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Shared helpers (also used by coordinator)
# ---------------------------------------------------------------------------

async def _get_csrf_from_page(session: aiohttp.ClientSession) -> str:
    """GET the login page and extract the CSRF token."""
    async with session.get(
        LOGIN_PAGE,
        headers={
            "user-agent": USER_AGENT,
            "accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        html = await resp.text()
    token = _extract_csrf_token(html)
    if not token:
        raise ValueError("cannot_get_token")
    return token


async def _login_credentials(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> dict[str, Any]:
    """POST credentials to /EAccount/Login/SignIn.

    Returns the full JSON body.  The caller inspects the response:
    - ``body["email"]`` present → direct login success
    - ``body["guid"]`` present → OTP verification required
    """
    csrf_token = await _get_csrf_from_page(session)

    async with session.post(
        LOGIN_API,
        headers={
            "user-agent": USER_AGENT,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://eservice.towngas.com",
            "referer": LOGIN_PAGE,
            "RequestVerificationToken": csrf_token,
        },
        data={
            "LoginID": username,
            "password": password,
            "Language": "en",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)

    body["_csrf_token"] = csrf_token
    return body


async def _send_otp(
    session: aiohttp.ClientSession,
    guid: str,
    csrf_token: str,
) -> dict[str, Any]:
    """Send the OTP verification code email."""
    async with session.post(
        GENERATE_OTP_API,
        headers={
            "user-agent": USER_AGENT,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://eservice.towngas.com",
            "referer": f"{LOGIN_PAGE}",
            "RequestVerificationToken": csrf_token,
        },
        data={
            "code": guid,
            "language": "en",
            "emailAddress": "",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)

    if not body.get("status"):
        raise ValueError("otp_send_failed")
    return body


async def _verify_otp(
    session: aiohttp.ClientSession,
    guid: str,
    session_token: str,
    otp_code: str,
    csrf_token: str,
) -> str:
    """Submit OTP code and return the new CSRF token.

    Raises ``ValueError("otp_invalid")`` on failure.
    """
    async with session.post(
        LOGIN_API,
        headers={
            "user-agent": USER_AGENT,
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://eservice.towngas.com",
            "referer": f"{LOGIN_PAGE}",
            "RequestVerificationToken": csrf_token,
        },
        data={
            "code": guid,
            "verifyCode": otp_code,
            "emailAddress": "",
            "sessionToken": session_token,
            "language": "en",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)

    if body.get("message"):
        raise ValueError("otp_invalid")

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
            "RequestVerificationToken": csrf_token,
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

class TownGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hong Kong Towngas."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str = ""
        self._password: str = ""
        self._csrf_token: str = ""
        self._accounts: list[str] = []
        # OTP flow state
        self._guid: str = ""
        self._session_token: str = ""

    # ------------------------------------------------------------------
    # Initial setup
    # ------------------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: collect username + password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]

            try:
                body = await _login_credentials(session, self._username, self._password)
            except ValueError as err:
                errors["base"] = str(err)
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Towngas login")
                errors["base"] = "unknown"

            if not errors:
                if body.get("email"):
                    # Direct login success
                    self._csrf_token = body.get("_csrf_token", "")
                    new_csrf = body.get("csrfToken")
                    if new_csrf:
                        self._csrf_token = new_csrf
                    self._accounts = await _get_accounts(session, self._csrf_token)
                    if len(self._accounts) == 1:
                        return self._create_entry(self._accounts[0])
                    return await self.async_step_account()

                if body.get("guid"):
                    # OTP required
                    self._guid = body["guid"]
                    self._session_token = body.get("sessionToken", "")
                    self._csrf_token = body.get("_csrf_token", "")
                    try:
                        await _send_otp(session, self._guid, self._csrf_token)
                    except ValueError as err:
                        errors["base"] = str(err)
                    if not errors:
                        return await self.async_step_otp()

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

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: enter OTP verification code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                new_csrf = await _verify_otp(
                    session,
                    self._guid,
                    self._session_token,
                    user_input["otp_code"],
                    self._csrf_token,
                )
                self._csrf_token = new_csrf
                self._accounts = await _get_accounts(session, new_csrf)
                if len(self._accounts) == 1:
                    return self._create_entry(self._accounts[0])
                return await self.async_step_account()
            except ValueError as err:
                errors["base"] = str(err)
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during OTP verification")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required("otp_code"): str}),
            errors=errors,
            description_placeholders={"email": self._username},
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: choose account number (only if multiple accounts exist)."""
        if user_input is not None:
            return self._create_entry(user_input[CONF_ACCOUNT_NO])

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_NO): vol.In(self._accounts)}),
        )

    def _create_entry(self, account_no: str) -> FlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=f"Towngas HK {account_no}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_ACCOUNT_NO: account_no,
            },
        )

    # ------------------------------------------------------------------
    # Re-authentication
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication. Auto-submit stored credentials."""
        if entry_data is None:
            entry = self._get_reauth_entry()
            entry_data = entry.data

        session = async_get_clientsession(self.hass)
        username = entry_data[CONF_USERNAME]
        password = entry_data[CONF_PASSWORD]

        try:
            body = await _login_credentials(session, username, password)
        except (ValueError, aiohttp.ClientResponseError, Exception):  # noqa: BLE001
            _LOGGER.debug("Reauth: stored credentials failed, showing form")
            return await self.async_step_reauth_form(entry_data)

        if body.get("email"):
            new_csrf = body.get("csrfToken", body.get("_csrf_token", ""))
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={CONF_USERNAME: username, CONF_PASSWORD: password},
            )

        if body.get("guid"):
            self._guid = body["guid"]
            self._session_token = body.get("sessionToken", "")
            self._csrf_token = body.get("_csrf_token", "")
            try:
                await _send_otp(session, self._guid, self._csrf_token)
            except ValueError:
                pass  # will show error on OTP form
            return await self.async_step_reauth_otp()

        return await self.async_step_reauth_form(entry_data)

    async def async_step_reauth_form(
        self,
        entry_data: dict[str, Any] | None = None,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Re-auth: show username + password form (when stored creds fail)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]

            try:
                body = await _login_credentials(session, self._username, self._password)
            except ValueError as err:
                errors["base"] = str(err)
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Towngas re-auth")
                errors["base"] = "unknown"

            if not errors:
                if body.get("email"):
                    self.hass.config_entries.async_update_entry(
                        self._get_reauth_entry(),
                        data={
                            **self._get_reauth_entry().data,
                            CONF_USERNAME: self._username,
                            CONF_PASSWORD: self._password,
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self._get_reauth_entry().entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                if body.get("guid"):
                    self._guid = body["guid"]
                    self._session_token = body.get("sessionToken", "")
                    self._csrf_token = body.get("_csrf_token", "")
                    try:
                        await _send_otp(session, self._guid, self._csrf_token)
                    except ValueError as err:
                        errors["base"] = str(err)
                    if not errors:
                        return await self.async_step_reauth_otp()

        # Pre-fill from stored credentials if available
        defaults = {}
        if entry_data:
            defaults = {
                vol.Optional(CONF_USERNAME, default=entry_data.get(CONF_USERNAME, "")): str,
                vol.Optional(CONF_PASSWORD, default=entry_data.get(CONF_PASSWORD, "")): str,
            }
        else:
            defaults = {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }

        return self.async_show_form(
            step_id="reauth_form",
            data_schema=vol.Schema(defaults),
            errors=errors,
        )

    async def async_step_reauth_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-auth: enter OTP verification code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                new_csrf = await _verify_otp(
                    session,
                    self._guid,
                    self._session_token,
                    user_input["otp_code"],
                    self._csrf_token,
                )
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={},
                )
            except ValueError as err:
                errors["base"] = str(err)
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauth OTP verification")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_otp",
            data_schema=vol.Schema({vol.Required("otp_code"): str}),
            errors=errors,
            description_placeholders={"email": self._username},
        )
