"""DataUpdateCoordinator for Hong Kong Towngas."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import re
from dataclasses import dataclass, asdict

import aiohttp
from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    BASE_URL,
    BILLING_API,
    CONF_BILLING_DATE,
    CONF_CACHED_DATA,
    CONF_CSRF_TOKEN,
    CONF_LAST_REFRESH,
    CONF_NEXT_REFRESH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LOGIN_API,
    LOGIN_PAGE,
    METER_API,
    NOTICE_API,
    SCAN_INTERVAL_MINUTES,
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
    "x-requested-with": "XMLHttpRequest",
    "sec-ch-ua": '"Not/A)Brand";v="99", "Chromium";v="148"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


def _calc_next_refresh(billing_date: datetime.date) -> datetime.datetime:
    """Calculate next refresh time as billingDate + 1 month.

    Towngas reads meters monthly, so next read should happen around the
    same time next month. We add 1 month to the last billing date.
    """
    month = billing_date.month + 1
    year = billing_date.year
    if month > 12:
        month = 1
        year += 1
    # Handle months with fewer days (e.g., Jan 31 + 1 month → Feb 28)
    day = min(billing_date.day, 28)
    return datetime.datetime(year, month, day, 0, 0, 0, tzinfo=datetime.timezone.utc)


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
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Towngas HK {account_no}",
            update_interval=datetime.timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self._session = session
        self._username = username
        self._password = password
        self.account_no = account_no
        self._config_entry = config_entry

        # Load persisted state
        self._csrf_token: str | None = config_entry.data.get(CONF_CSRF_TOKEN)
        self._billing_date: datetime.date | None = self._parse_date(
            config_entry.data.get(CONF_BILLING_DATE)
        )
        self._next_refresh: datetime.datetime | None = self._parse_datetime(
            config_entry.data.get(CONF_NEXT_REFRESH)
        )
        self._last_refresh: datetime.datetime | None = self._parse_datetime(
            config_entry.data.get(CONF_LAST_REFRESH)
        )
        # Restore cached data from config entry
        self._restored_data: TownGasData | None = None
        cached_json = config_entry.data.get(CONF_CACHED_DATA)
        if cached_json:
            try:
                d = json.loads(cached_json)
                self._restored_data = TownGasData(
                    latest_consumption_mj=d.get("latest_consumption_mj"),
                    latest_consumption_units=d.get("latest_consumption_units"),
                    latest_meter_reading=d.get("latest_meter_reading"),
                    latest_reading_type=d.get("latest_reading_type", ""),
                    latest_reading_date=self._parse_date(d.get("latest_reading_date")),
                    latest_reading_text=d.get("latest_reading_text"),
                    is_show_latest_reading=d.get("is_show_latest_reading", False),
                    is_show_prediction=d.get("is_show_prediction", False),
                    current_balance=d.get("current_balance"),
                    bill_amount_due=d.get("bill_amount_due"),
                    bill_due_date=self._parse_date(d.get("bill_due_date")),
                    is_overdue=d.get("is_overdue", False),
                    is_auto_pay=d.get("is_auto_pay", False),
                    is_ibill=d.get("is_ibill", False),
                    account_status=d.get("account_status", ""),
                    balance_updated=d.get("balance_updated", ""),
                )
                _LOGGER.debug(
                    "Towngas: restored cached data (consumption=%s, balance=%s)",
                    self._restored_data.latest_consumption_mj,
                    self._restored_data.current_balance,
                )
            except (json.JSONDecodeError, TypeError) as err:
                _LOGGER.warning("Towngas: failed to restore cached data: %s", err)
        # Reauth cooldown — don't trigger reauth more than once per 10 minutes
        self._last_reauth_time: datetime.datetime | None = None

    @staticmethod
    def _parse_date(val: str | None) -> datetime.date | None:
        if not val:
            return None
        try:
            return datetime.date.fromisoformat(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(val: str | None) -> datetime.datetime | None:
        if not val:
            return None
        try:
            return datetime.datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return None

    def _persist_state(self, data: TownGasData) -> None:
        """Save state to config_entry.data for survival across restarts."""
        now = dt_util.utcnow()
        self._last_refresh = now
        updates: dict = {
            CONF_LAST_REFRESH: now.isoformat(),
        }

        # Persist actual sensor data as JSON
        try:
            d = asdict(data)
            # Convert date objects to strings for JSON serialization
            for key in ("latest_reading_date", "bill_due_date"):
                if d.get(key) is not None:
                    d[key] = d[key].isoformat() if hasattr(d[key], "isoformat") else str(d[key])
            updates[CONF_CACHED_DATA] = json.dumps(d, default=str)
        except Exception:  # noqa: BLE001
            pass

        if self._csrf_token:
            updates[CONF_CSRF_TOKEN] = self._csrf_token

        if data.latest_reading_date:
            self._billing_date = data.latest_reading_date
            updates[CONF_BILLING_DATE] = data.latest_reading_date.isoformat()

        if self._billing_date:
            self._next_refresh = _calc_next_refresh(self._billing_date)
            updates[CONF_NEXT_REFRESH] = self._next_refresh.isoformat()

        if updates:
            self.hass.config_entries.async_update_entry(
                self._config_entry, data={**self._config_entry.data, **updates}
            )

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
        """Get fresh CSRF token — matches browser behavior."""
        # Step 1: load login page (sets cookies)
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.get(
                LOGIN_PAGE,
                headers={"user-agent": USER_AGENT, "accept": "text/html,application/xhtml+xml,*/*"},
            )
            resp.raise_for_status()

        # Step 2: get fresh CSRF from API (matches browser)
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp2 = await self._session.get(
                f"{BASE_URL}/Common/GetCSRFToken",
                headers={**COMMON_HEADERS, "accept": "application/json, text/javascript, */*; q=0.01"},
            )
            resp2.raise_for_status()
            body = await resp2.json(content_type=None)
            token = body.get("csrfToken")
            if token:
                return token

        # Fallback: extract from HTML
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
        # Overdue if balance > 0 (unpaid amount)
        data.is_overdue = (
            data.current_balance is not None and data.current_balance > 0
        )
        data.is_auto_pay = raw.get("isAutoPay", "N") == "Y"
        data.is_ibill = bool(raw.get("isIbillService", False))
        data.account_status = raw.get("accountNoStatus", "")
        data.balance_updated = raw.get("strUpdatedDate", "")

    # ------------------------------------------------------------------
    # DataUpdateCoordinator entry point
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> TownGasData:
        """Fetch all data - called by DataUpdateCoordinator every 24h.

        Smart refresh logic:
        1. If now < next_refresh AND we have last data → return cached, skip login
        2. If fetch is due → try cached CSRF first
        3. If CSRF fails → fresh login
        4. After fetch → persist new billingDate and nextRefresh
        """
        now = dt_util.utcnow()
        interval = datetime.timedelta(minutes=SCAN_INTERVAL_MINUTES)

        # Step 0: Smart skip — if last refresh was within interval, skip
        if self._last_refresh and (now - self._last_refresh) < interval:
            if self._restored_data is not None:
                _LOGGER.debug(
                    "Towngas: using cached data (consumption=%s, balance=%s)",
                    self._restored_data.latest_consumption_mj,
                    self._restored_data.current_balance,
                )
                return self._restored_data
            if self.data is not None:
                _LOGGER.debug("Towngas: using in-memory data")
                return self.data
            _LOGGER.debug("Towngas: no cached data available")
            return TownGasData()

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
                    self._persist_state(data)
                    return data
                except (aiohttp.ClientError, UpdateFailed):
                    _LOGGER.debug("Cached session expired, re-logging in")
                    self._csrf_token = None

            # Step 2: re-login from scratch
            if not self._password:
                _LOGGER.warning(
                    "Towngas: password not saved — showing cached data. "
                    "Re-authenticate from Settings → Integrations to get fresh data."
                )
                if self._restored_data is not None:
                    self.data = self._restored_data
                    return self._restored_data
                return TownGasData()

            page_token = await self._get_csrf_token()
            body = await self._login_raw(page_token)

            if body.get("guid"):
                # OTP required — keep stale data visible, trigger reauth flow
                self._csrf_token = None
                if self._restored_data is not None:
                    self.data = self._restored_data
                    _LOGGER.warning(
                        "Towngas: OTP required — showing cached data. "
                        "Re-authenticate from Settings → Integrations."
                    )
                else:
                    _LOGGER.warning("Towngas: OTP required — no cached data available")
                raise ConfigEntryAuthFailed("OTP verification required")

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
            self._persist_state(data)
        except (UpdateFailed, ConfigEntryAuthFailed):
            raise
        except asyncio.TimeoutError:
            raise UpdateFailed(
                "Connection to Towngas timed out — check your internet connection"
            )
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err
        return data
