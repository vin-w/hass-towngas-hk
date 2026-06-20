"""DataUpdateCoordinator for Hong Kong Towngas."""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from dataclasses import dataclass, field

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BILLING_API,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGIN_API,
    LOGIN_PAGE,
    METER_API,
    NOTICE_API,
    SCAN_INTERVAL_HOURS,
    UNITS_TO_MJ,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared CSRF token extractor (also imported by config_flow)
# ---------------------------------------------------------------------------

def extract_csrf_token(html: str) -> str | None:
    """Extract CSRF token from Towngas login page HTML."""
    for meta_name in ("csrf-token", "RequestVerificationToken", "_csrf"):
        for pattern in (
            rf'<meta[^>]+name=["\']{re.escape(meta_name)}["\'][^>]+content=["\'](CfDJ8[^"\']+)',
            rf'<meta[^>]+content=["\'](CfDJ8[^"\']+)["\'][^>]+name=["\']{re.escape(meta_name)}',
        ):
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
    match = re.search(r'["\' ](CfDJ8[A-Za-z0-9_\-]{60,})["\']', html)
    return match.group(1) if match else None


COMMON_HEADERS = {
    "user-agent": USER_AGENT,
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "x-requested-with": "XMLHttpRequest",
    "origin": "https://eservice.towngas.com",
    "referer": LOGIN_PAGE,
    "pragma": "no-cache",
    "cache-control": "no-cache",
}


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class TownGasData:
    """All data fetched for one Towngas account."""

    # Latest meter reading from historyList[0]
    latest_consumption_mj: float | None = None     # consumption × 48
    latest_consumption_units: int | None = None     # raw units from API
    latest_meter_reading: int | None = None         # cumulative meter total
    latest_reading_type: str = ""                   # Remote / Actual / Estimate
    latest_reading_date: datetime.date | None = None
    latest_reading_text: str | None = None          # pre-formatted text from API
    is_show_latest_reading: bool = False            # isShowLatestMeterReading
    is_show_prediction: bool = False                # isShowPredictionBar

    # Account / billing notice
    current_balance: float | None = None
    bill_amount_due: float | None = None
    bill_due_date: datetime.date | None = None
    is_overdue: bool = False
    is_auto_pay: bool = False
    is_ibill: bool = False
    account_status: str = ""
    balance_updated: str = ""


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class TownGasCoordinator(DataUpdateCoordinator[TownGasData]):
    """Single coordinator shared by all Towngas entities for one account."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        account_no: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Towngas HK {account_no}",
            update_interval=datetime.timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self._session = session
        self._username = username
        self._password = password
        self.account_no = account_no
        self._csrf_token: str | None = None  # cached between polls

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo shared by all entities for this account."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.account_no)},
            name=f"Towngas HK Account {self.account_no}",
            model="eService",
            entry_type="service",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_csrf_token(self) -> str:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.get(
                LOGIN_PAGE,
                headers={"user-agent": USER_AGENT, "accept": "text/html,application/xhtml+xml,*/*"},
            )
            resp.raise_for_status()
            html = await resp.text()
        token = extract_csrf_token(html)
        if not token:
            raise UpdateFailed("Could not extract CSRF token from Towngas login page")
        return token

    async def _login_raw(self, csrf_token: str) -> dict:
        """POST credentials and return the full JSON response body.

        Returns ``{email, csrfToken}`` on success or ``{guid, sessionToken}``
        when OTP verification is required.
        """
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                LOGIN_API,
                headers={
                    **COMMON_HEADERS,
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "RequestVerificationToken": csrf_token,
                },
                data={
                    "LoginID": self._username,
                    "password": self._password,
                    "Language": "en",
                },
            )
            resp.raise_for_status()
            body = await resp.json(content_type=None)
        return body

    async def _fetch_meter(self, csrf_token: str, data: TownGasData) -> None:
        """Fetch meter data and populate TownGasData.

        The API returns two main data structures:

        - ``historyList``: Chronological list of actual monthly meter readings.
          Each entry has ``meterReading`` (cumulative units), ``consumption``
          (monthly usage in units, where 1 unit = 48 MJ), ``readingType``
          (Remote/Actual/Estimate), and ``billingDate``.

        - ``chartBarList``: Bi-monthly pairs for chart display, plus a
          prediction entry (odd-month, ``isEstimateMonth: true``) when
          available.

        Priority: ``historyList`` is always more up-to-date than
        ``chartBarList`` because actual meter reads (e.g. manual reads)
        appear in historyList before chartBarList updates.

        Top-level flags:
        - ``isShowLatestMeterReading``: true when a fresh reading is available
        - ``isShowPredictionBar``: true when a prediction forecast exists
        - ``latestMeterReadingText``: pre-formatted string for display
        """
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                METER_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={
                    "accountNo": self.account_no,
                    "language": "en",
                    "isAccountInfo": "true",
                    "isHousehold": "true",
                },
            )
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

        # --- historyList → primary source for consumption sensor ---
        history = raw.get("historyList", [])
        if history:
            h = history[0]
            try:
                data.latest_consumption_units = int(h["consumption"])
                data.latest_consumption_mj = data.latest_consumption_units * UNITS_TO_MJ
            except (ValueError, TypeError, KeyError):
                data.latest_consumption_units = None
                data.latest_consumption_mj = None

            data.latest_meter_reading = h.get("meterReading")
            data.latest_reading_type = h.get("readingType", "")

            billing_date = h.get("billingDate")
            if billing_date:
                try:
                    data.latest_reading_date = datetime.date.fromisoformat(billing_date[:10])
                except (ValueError, AttributeError):
                    data.latest_reading_date = None

        # --- Top-level flags ---
        data.is_show_latest_reading = raw.get("isShowLatestMeterReading", False)
        data.is_show_prediction = raw.get("isShowPredictionBar", False)
        data.latest_reading_text = raw.get("latestMeterReadingText")

    async def _fetch_billing(self, csrf_token: str, data: TownGasData) -> None:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                BILLING_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={"accountNo": self.account_no},
            )
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

        bills: list[dict] = []
        for record in raw.get("list", []):
            try:
                total = float(record["total"].replace("HK $", "").replace(",", "").strip())
            except (ValueError, AttributeError):
                total = 0.0
            bills.append({"time": record["strBillDate"], "total": total})

        # Use latest bill for sensors
        if bills:
            data.bill_amount_due = bills[0]["total"]
            bill_date = bills[0]["time"]
            if bill_date:
                try:
                    data.bill_due_date = datetime.date.fromisoformat(bill_date[:10])
                except (ValueError, AttributeError):
                    data.bill_due_date = None

    async def _fetch_notice(self, csrf_token: str, data: TownGasData) -> None:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                NOTICE_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={"accountNo": self.account_no},
            )
            resp.raise_for_status()
            raw = await resp.json(content_type=None)

        def _parse_amount(val: str | None) -> float | None:
            if not val:
                return None
            try:
                return float(val.replace(",", "").strip())
            except ValueError:
                return None

        data.current_balance = _parse_amount(raw.get("currentAccountBalance"))
        data.is_overdue = raw.get("isOverdueBill", "N") == "Y"
        data.is_auto_pay = raw.get("isAutoPay", "N") == "Y"
        data.is_ibill = bool(raw.get("isIbillService", False))
        data.account_status = raw.get("accountNoStatus", "")
        data.balance_updated = raw.get("strUpdatedDate", "")

    # ------------------------------------------------------------------
    # DataUpdateCoordinator entry point
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> TownGasData:
        """Fetch all data - called by DataUpdateCoordinator on schedule."""
        data = TownGasData()
        try:
            # Step 1: try cached session
            if self._csrf_token:
                try:
                    await asyncio.gather(
                        self._fetch_meter(self._csrf_token, data),
                        self._fetch_billing(self._csrf_token, data),
                        self._fetch_notice(self._csrf_token, data),
                    )
                    return data
                except (aiohttp.ClientError, UpdateFailed):
                    _LOGGER.debug("Cached session expired, re-logging in")
                    self._csrf_token = None

            # Step 2: re-login from scratch
            page_token = await self._get_csrf_token()
            body = await self._login_raw(page_token)

            if body.get("guid"):
                # OTP required — can't handle silently, trigger reauth
                self._csrf_token = None
                self.async_config_entry_login_failed()
                raise UpdateFailed("OTP verification required — reauth triggered")

            if not body.get("email"):
                raise UpdateFailed("Towngas login failed - invalid credentials")

            _LOGGER.debug("Towngas logged in as %s", body["email"])
            new_csrf = body.get("csrfToken", page_token)
            self._csrf_token = new_csrf

            # Step 3: fetch data with fresh session
            await asyncio.gather(
                self._fetch_meter(new_csrf, data),
                self._fetch_billing(new_csrf, data),
                self._fetch_notice(new_csrf, data),
            )
        except UpdateFailed:
            raise
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err
        return data
