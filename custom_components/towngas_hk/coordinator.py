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

    # Gas meter
    current_month_consumption: float | None = None
    next_month_consumption: float | None = None
    # month strings associated with the above values ("Feb 2026" etc.)
    current_month: str | None = None
    next_month: str | None = None
    # flags to indicate whether the month value was estimated
    is_current_month_estimate: bool = False
    is_next_month_estimate: bool = False
    readings: list[dict] = field(default_factory=list)
    bills: list[dict] = field(default_factory=list)

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
            name=f"Towngas {account_no}",
            update_interval=datetime.timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self._session = session
        self._username = username
        self._password = password
        self.account_no = account_no

    @property
    def device_info(self) -> DeviceInfo:
        """DeviceInfo shared by all entities for this account."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.account_no)},
            name=f"Towngas Account {self.account_no}",
            manufacturer="Unofficial",
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

    async def _login(self, csrf_token: str) -> str:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                LOGIN_API,
                headers={
                    **COMMON_HEADERS,
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "requestverificationtoken": csrf_token,
                },
                data={
                    "LoginID": self._username,
                    "UserName": self._username,
                    "password": self._password,
                    "Password": self._password,
                    "Language": "en",
                },
            )
            resp.raise_for_status()
            body = await resp.json(content_type=None)
        if not body.get("email"):
            raise UpdateFailed("Towngas login failed - invalid credentials")
        _LOGGER.debug("Towngas logged in as %s", body["email"])
        return body.get("csrfToken", csrf_token)

    async def _fetch_meter(self, csrf_token: str, data: TownGasData) -> None:
        """
        Fetch meter statistics and update "data" with current and prediction
        values.

        The response contains a sequence of records in ``chartBarList``.  Each
        record may provide two months of consumption (``strMonth1``/``strMonth2``
        and ``consumption1``/``consumption2``) or a forecast entry marked by
        ``isEstimateMonth`` where ``strPredictionConsumptionMonth`` designates
        the target month and ``predictionConsumption`` gives the estimated
        amount.

        We generate:

        * ``data.readings`` – a chronological list of all values, used by
          history sensors.
                * ``data.current_month_consumption`` & ``current_month`` – the
                    value matched to the current calendar month (or, if none found,
                    the most recent actual reading).
                * ``data.next_month_consumption`` & ``next_month`` –
                    the value matched to the next calendar month.
                * ``data.is_current_month_estimate`` / ``data.is_next_month_estimate`` –
                    flags indicating whether the assigned value was taken from a
          forecast row.

        If no matching entry is found for current month, ``current_month_consumption``
        will be set to the most recent actual reading (or ``0.0`` if the list
        is empty).  ``next_month_consumption`` defaults to ``0.0`` when no
        next‑month value is available.  Estimate flags remain ``False`` by
        default.

        The logic handles both regular and estimate rows; examples are
        documented in the class docstring above.
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

        readings: list[dict] = []
        latest_actual: float | None = None

        now = datetime.datetime.now()
        current_month_str = now.strftime("%b %Y")
        next_month_dt = (now.replace(day=1) + datetime.timedelta(days=31)).replace(day=1)
        next_month_str = next_month_dt.strftime("%b %Y")

        for record in raw.get("chartBarList", []):
            # process normal consumption entries
            if record.get("strMonth1") and record.get("consumption1"):
                val = float(record["consumption1"])
                readings.append({"time": record["strMonth1"], "mj": val})
                latest_actual = val
                if record["strMonth1"] == current_month_str:
                    data.current_month_consumption = val
                    data.current_month = current_month_str
                    data.is_current_month_estimate = False
                if record["strMonth1"] == next_month_str:
                    data.next_month_consumption = val
                    data.next_month = next_month_str
                    data.is_next_month_estimate = False
            if record.get("strMonth2") and record.get("consumption2"):
                val = float(record["consumption2"])
                readings.append({"time": record["strMonth2"], "mj": val})
                latest_actual = val
                if record["strMonth2"] == current_month_str:
                    data.current_month_consumption = val
                    data.current_month = current_month_str
                    data.is_current_month_estimate = False
                if record["strMonth2"] == next_month_str:
                    data.next_month_consumption = val
                    data.next_month = next_month_str
                    data.is_next_month_estimate = False

            # process forecast entry
            if record.get("isEstimateMonth"):
                pred_month = record.get("strPredictionConsumptionMonth")
                if record.get("predictionConsumption") and pred_month:
                    val = float(record["predictionConsumption"])
                    readings.append({"time": pred_month, "mj": val, "estimated": True})
                    if pred_month == current_month_str:
                        data.current_month_consumption = val
                        data.current_month = pred_month
                        data.is_current_month_estimate = True
                    elif pred_month == next_month_str:
                        data.next_month_consumption = val
                        data.next_month = pred_month
                        data.is_next_month_estimate = True

        readings.reverse()
        data.readings = readings

        # if no explicit match for current month, fall back to most recent
        # actual reading (latest_actual) or zero if no data at all
        if data.current_month_consumption is None:
            if latest_actual is not None:
                data.current_month_consumption = latest_actual
            else:
                data.current_month_consumption = 0.0
        # ensure we always have numeric next-month value (0 if not found)
        if data.next_month_consumption is None:
            data.next_month_consumption = 0.0

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
        data.bills = bills

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
        data.bill_amount_due = _parse_amount(raw.get("billAmountDue"))
        data.is_overdue = raw.get("isOverdueBill", "N") == "Y"
        data.is_auto_pay = raw.get("isAutoPay", "N") == "Y"
        data.is_ibill = bool(raw.get("isIbillService", False))
        data.account_status = raw.get("accountNoStatus", "")
        data.balance_updated = raw.get("strUpdatedDate", "")

        raw_due = raw.get("billDueDate")
        if raw_due:
            try:
                data.bill_due_date = datetime.date.fromisoformat(raw_due[:10])
            except ValueError:
                data.bill_due_date = None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator entry point
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> TownGasData:
        """Fetch all data - called by DataUpdateCoordinator on schedule."""
        data = TownGasData()
        try:
            csrf_token = await self._get_csrf_token()
            csrf_token = await self._login(csrf_token)
            await asyncio.gather(
                self._fetch_meter(csrf_token, data),
                self._fetch_billing(csrf_token, data),
                self._fetch_notice(csrf_token, data),
            )
        except UpdateFailed:
            raise
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Unexpected error: {err}") from err
        return data
