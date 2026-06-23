"""Config flow for Hong Kong Towngas."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ACCOUNT_API,
    AUTH_PAGE,
    CONF_ACCOUNT_NO,
    CONF_CSRF_TOKEN,
    DEFAULT_TIMEOUT,
    DOMAIN,
    GENERATE_OTP_API,
    LOGIN_API,
    LOGIN_PAGE,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

from .coordinator import COMMON_HEADERS, extract_csrf_token as _extract_csrf_token  # noqa: E402

_TIMEOUT = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Shared helpers (also used by coordinator)
# ---------------------------------------------------------------------------

async def _get_csrf_from_page(session: aiohttp.ClientSession) -> str:
    """GET the login page and extract the CSRF token.

    Two-step process matching browser behavior:
    1. GET login page → sets cookies
    2. GET /Common/GetCSRFToken → fresh CSRF via API
    """
    # Step 1: load the page (sets Incapsula/antiforgery cookies)
    async with session.get(
        LOGIN_PAGE,
        headers={
            "user-agent": USER_AGENT,
            "accept": "text/html,application/xhtml+xml,*/*",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()

    # Step 2: get fresh CSRF token from API (matches browser behavior)
    async with session.get(
        f"https://eservice.towngas.com/Common/GetCSRFToken",
        headers={
            **COMMON_HEADERS,
            "accept": "application/json, text/javascript, */*; q=0.01",
        },
        timeout=_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        body = await resp.json(content_type=None)
        token = body.get("csrfToken")
        if token:
            return token

    # Fallback: extract from HTML
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
            **COMMON_HEADERS,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
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
            **COMMON_HEADERS,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "referer": f"{AUTH_PAGE}?code={guid}",
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
            **COMMON_HEADERS,
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "referer": f"{AUTH_PAGE}?code={guid}",
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
            **COMMON_HEADERS,
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
        # Last API error message for display
        self._api_error: str = ""
        # Whether to save password in config entry
        self._save_password: bool = False

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
            self._save_password = user_input.get("save_password", False)

            try:
                body = await _login_credentials(session, self._username, self._password)
            except ValueError as err:
                self._api_error = str(err)
                errors["base"] = "api_error"
            except aiohttp.ClientResponseError:
                self._api_error = "Failed to connect to Towngas eService"
                errors["base"] = "api_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Towngas login")
                self._api_error = "Unexpected error. Check Home Assistant logs."
                errors["base"] = "api_error"

            if not errors:
                if body.get("message"):
                    self._api_error = body["message"]
                    errors["base"] = "api_error"
                elif body.get("email"):
                    # Direct login success
                    self._csrf_token = body.get("_csrf_token", "")
                    new_csrf = body.get("csrfToken")
                    if new_csrf:
                        self._csrf_token = new_csrf
                    self._accounts = await _get_accounts(session, self._csrf_token)
                    if len(self._accounts) == 1:
                        await self._async_set_unique_and_abort_if_configured(self._accounts[0])
                        return self._create_entry(self._accounts[0])
                    return await self.async_step_account()

                if body.get("guid"):
                    # OTP required
                    self._guid = body["guid"]
                    self._session_token = body.get("sessionToken", "")
                    # Get FRESH CSRF token after login (matches browser behavior)
                    try:
                        fresh_resp = await session.get(
                            "https://eservice.towngas.com/Common/GetCSRFToken",
                            headers={**COMMON_HEADERS, "accept": "application/json"},
                            timeout=_TIMEOUT,
                        )
                        fresh_resp.raise_for_status()
                        fresh_body = await fresh_resp.json(content_type=None)
                        self._csrf_token = fresh_body.get("csrfToken", self._csrf_token)
                    except Exception:  # noqa: BLE001
                        pass  # fallback to existing csrf_token
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
                    vol.Optional("save_password", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={"error": self._api_error},
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
                    await self._async_set_unique_and_abort_if_configured(self._accounts[0])
                    return self._create_entry(self._accounts[0])
                return await self.async_step_account()
            except ValueError as err:
                self._api_error = str(err)
                errors["base"] = "api_error"
            except aiohttp.ClientResponseError:
                self._api_error = "Failed to connect to Towngas eService"
                errors["base"] = "api_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during OTP verification")
                self._api_error = "Unexpected error. Check Home Assistant logs."
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required("otp_code"): str}),
            errors=errors,
            description_placeholders={"email": self._username, "error": self._api_error},
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: choose account number (only if multiple accounts exist)."""
        if user_input is not None:
            account_no = user_input[CONF_ACCOUNT_NO]
            await self._async_set_unique_and_abort_if_configured(account_no)
            return self._create_entry(account_no)

        return self.async_show_form(
            step_id="account",
            data_schema=vol.Schema({vol.Required(CONF_ACCOUNT_NO): vol.In(self._accounts)}),
        )

    def _create_entry(self, account_no: str) -> FlowResult:
        """Create the config entry."""
        data = {
            CONF_USERNAME: self._username,
            CONF_ACCOUNT_NO: account_no,
            CONF_CSRF_TOKEN: self._csrf_token,
        }
        if self._save_password:
            data[CONF_PASSWORD] = self._password
        return self.async_create_entry(
            title=f"Towngas HK {account_no}",
            data=data,
        )

    async def _async_set_unique_and_abort_if_configured(self, account_no: str) -> bool:
        """Set unique ID and abort if already configured. Returns True if aborted."""
        await self.async_set_unique_id(f"towngas_hk_{account_no}")
        self._abort_if_unique_id_configured()
        return False

    # ------------------------------------------------------------------
    # Re-authentication
    # ------------------------------------------------------------------

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle re-authentication. Show password form."""
        entry = self._get_reauth_entry()
        await self.async_set_unique_id(entry.unique_id)
        self._username = entry.data.get(CONF_USERNAME, "")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
            }),
            description_placeholders={"email": self._username},
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication password submission."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            _LOGGER.debug("Reauth confirm submitted")
            session = async_get_clientsession(self.hass)
            self._username = entry.data.get(CONF_USERNAME, "")
            self._password = user_input[CONF_PASSWORD]
            self._save_password = user_input.get("save_password", False)

            try:
                body = await _login_credentials(session, self._username, self._password)
            except ValueError as err:
                self._api_error = str(err)
                errors["base"] = "api_error"
            except aiohttp.ClientResponseError:
                self._api_error = "Failed to connect to Towngas eService"
                errors["base"] = "api_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during Towngas re-auth")
                self._api_error = "Unexpected error. Check Home Assistant logs."
                errors["base"] = "api_error"

            if not errors:
                _LOGGER.debug("Reauth: login response keys=%s", list(body.keys()))
                if body.get("message"):
                    _LOGGER.debug("Reauth: login failed message=%s", body["message"])
                    self._api_error = body["message"]
                    errors["base"] = "api_error"
                elif body.get("email"):
                    # Direct login success — still need OTP since it's always enabled
                    pass
                elif body.get("guid"):
                    # OTP required (expected since OTP is always enabled)
                    self._guid = body["guid"]
                    self._session_token = body.get("sessionToken", "")
                    # Get FRESH CSRF token after login
                    try:
                        fresh_resp = await session.get(
                            "https://eservice.towngas.com/Common/GetCSRFToken",
                            headers={**COMMON_HEADERS, "accept": "application/json"},
                            timeout=_TIMEOUT,
                        )
                        fresh_resp.raise_for_status()
                        fresh_body = await fresh_resp.json(content_type=None)
                        self._csrf_token = fresh_body.get("csrfToken", self._csrf_token)
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        await _send_otp(session, self._guid, self._csrf_token)
                    except ValueError as err:
                        self._api_error = str(err)
                        errors["base"] = "api_error"
                    if not errors:
                        return self.async_show_form(
                            step_id="reauth_otp",
                            data_schema=vol.Schema({vol.Required("otp_code"): str}),
                            description_placeholders={"email": self._username, "error": ""},
                        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")): str,
                vol.Optional("save_password", default=CONF_PASSWORD in entry.data): bool,
            }),
            errors=errors,
            description_placeholders={"email": self._username, "error": self._api_error},
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
                entry = self._get_reauth_entry()
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_CSRF_TOKEN: new_csrf,
                    },
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except ValueError as err:
                self._api_error = str(err)
                errors["base"] = "api_error"
            except aiohttp.ClientResponseError:
                self._api_error = "Failed to connect to Towngas eService"
                errors["base"] = "api_error"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during reauth OTP verification")
                self._api_error = "Unexpected error. Check Home Assistant logs."
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="reauth_otp",
            data_schema=vol.Schema({vol.Required("otp_code"): str}),
            errors=errors,
            description_placeholders={"email": self._username, "error": self._api_error},
        )
