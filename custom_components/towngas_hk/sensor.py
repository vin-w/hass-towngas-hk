"""Sensor platform for Hong Kong Towngas."""

from __future__ import annotations

import datetime
import logging
import re

import aiohttp
import async_timeout
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CURRENCY_DOLLAR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import (
    BILLING_API,
    CONF_ACCOUNT_NO,
    DEFAULT_TIMEOUT,
    LOGIN_API,
    LOGIN_PAGE,
    METER_API,
    NOTICE_API,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(hours=1)

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


def _extract_csrf_token(html: str) -> str | None:
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Towngas sensors from a config entry."""
    data = config_entry.data
    session = async_get_clientsession(hass)
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    account_no = data[CONF_ACCOUNT_NO]

    coordinator = TownGasCoordinator(session, username, password, account_no)

    async_add_entities(
        [
            TownGasConsumptionSensor(coordinator, account_no),
            TownGasBalanceSensor(coordinator, account_no),
            TownGasBillAmountSensor(coordinator, account_no),
            TownGasBillDateSensor(coordinator, account_no),
        ],
        update_before_add=True,
    )


def _device_info(account_no: str) -> dict:
    """Shared device info for all Towngas entities."""
    return {
        "identifiers": {("towngas_hk", account_no)},
        "name": f"Towngas Account {account_no}",
        "manufacturer": "Unofficial",
        "model": "eService",
        "entry_type": "service",
    }


class TownGasCoordinator:
    """Shared data coordinator — logs in once and fetches all APIs per update cycle."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        account_no: str,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._account_no = account_no

        # Shared data storage
        self.readings: list[dict] = []
        self.bills: list[dict] = []
        self.current_consumption: float | None = None
        self.current_balance: float | None = None
        self.bill_amount_due: float | None = None
        self.bill_due_date: datetime.date | None = None
        self.is_overdue: bool = False
        self.is_auto_pay: bool = False
        self.is_ibill: bool = False
        self.account_status: str = ""
        self.balance_updated: str = ""

    async def _get_csrf_token(self) -> str:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.get(
                LOGIN_PAGE,
                headers={"user-agent": USER_AGENT, "accept": "text/html,application/xhtml+xml,*/*"},
            )
            resp.raise_for_status()
            html = await resp.text()
        token = _extract_csrf_token(html)
        if not token:
            raise RuntimeError("Could not extract CSRF token")
        return token

    async def _login(self, csrf_token: str) -> str:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
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
            raise RuntimeError("Towngas login failed")
        _LOGGER.debug("Towngas logged in as %s", body["email"])
        return body.get("csrfToken", csrf_token)

    async def _fetch_meter_readings(self, csrf_token: str) -> None:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                METER_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={"accountNo": self._account_no, "language": "en", "isAccountInfo": "true", "isHousehold": "true"},
            )
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        readings: list[dict] = []
        for record in data.get("chartBarList", []):
            if record.get("strMonth1") and record.get("consumption1"):
                readings.append({"time": record["strMonth1"], "mj": record["consumption1"]})
            if record.get("strMonth2") and record.get("consumption2"):
                readings.append({"time": record["strMonth2"], "mj": record["consumption2"]})
            if record.get("isEstimateMonth") and record.get("predictionConsumption") and record.get("strMonth1"):
                readings.append({"time": record["strMonth1"], "mj": record["predictionConsumption"], "estimated": True})
                self.current_consumption = float(record["predictionConsumption"])
        readings.reverse()
        self.readings = readings

    async def _fetch_billing(self, csrf_token: str) -> None:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                BILLING_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={"accountNo": self._account_no},
            )
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        bills: list[dict] = []
        for record in data.get("list", []):
            total = record["total"].replace("HK $", "").replace(",", "").replace(".00", "").strip()
            bills.append({"time": record["strBillDate"], "total": int(total)})
        self.bills = bills

    async def _fetch_notice(self, csrf_token: str) -> None:
        async with async_timeout.timeout(DEFAULT_TIMEOUT):
            resp = await self._session.post(
                NOTICE_API,
                headers={**COMMON_HEADERS, "requestverificationtoken": csrf_token},
                data={"accountNo": self._account_no},
            )
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        def _clean_amount(val: str | None) -> float | None:
            if not val:
                return None
            try:
                return float(val.replace(",", "").strip())
            except ValueError:
                return None

        self.current_balance = _clean_amount(data.get("currentAccountBalance"))
        self.bill_amount_due = _clean_amount(data.get("billAmountDue"))
        self.is_overdue = data.get("isOverdueBill", "N") == "Y"
        self.is_auto_pay = data.get("isAutoPay", "N") == "Y"
        self.is_ibill = bool(data.get("isIbillService", False))
        self.account_status = data.get("accountNoStatus", "")
        self.balance_updated = data.get("strUpdatedDate", "")

        raw_due = data.get("billDueDate")
        if raw_due:
            try:
                self.bill_due_date = datetime.date.fromisoformat(raw_due[:10])
            except ValueError:
                self.bill_due_date = None
        else:
            self.bill_due_date = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Login once and refresh all data."""
        try:
            csrf_token = await self._get_csrf_token()
            csrf_token = await self._login(csrf_token)
            await self._fetch_meter_readings(csrf_token)
            await self._fetch_billing(csrf_token)
            await self._fetch_notice(csrf_token)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Error updating Towngas data for account %s", self._account_no)


class TownGasBaseSensor(SensorEntity):
    """Base class for all Towngas sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        self._coordinator = coordinator
        self._account_no = account_no

    @property
    def device_info(self) -> dict:
        return _device_info(self._account_no)

    async def async_update(self) -> None:
        await self._coordinator.async_update()


class TownGasConsumptionSensor(TownGasBaseSensor):
    """Monthly gas consumption in MJ."""

    _attr_name = "Gas Consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "towngas_hk:icon"

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        super().__init__(coordinator, account_no)
        self._attr_unique_id = f"towngas_hk_{account_no}_consumption"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.current_consumption

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "account_no": self._account_no,
            "readings": self._coordinator.readings,
            "bills": self._coordinator.bills,
        }


class TownGasBalanceSensor(TownGasBaseSensor):
    """Current account balance in HKD."""

    _attr_name = "Current Balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        super().__init__(coordinator, account_no)
        self._attr_unique_id = f"towngas_hk_{account_no}_balance"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.current_balance

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "updated_date": self._coordinator.balance_updated,
            "auto_pay": self._coordinator.is_auto_pay,
            "ibill": self._coordinator.is_ibill,
            "account_status": self._coordinator.account_status,
        }


class TownGasBillAmountSensor(TownGasBaseSensor):
    """Latest bill amount due in HKD."""

    _attr_name = "Bill Amount Due"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:receipt"

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        super().__init__(coordinator, account_no)
        self._attr_unique_id = f"towngas_hk_{account_no}_bill_amount"

    @property
    def native_value(self) -> float | None:
        return self._coordinator.bill_amount_due


class TownGasBillDateSensor(TownGasBaseSensor):
    """Bill due date."""

    _attr_name = "Bill Due Date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        super().__init__(coordinator, account_no)
        self._attr_unique_id = f"towngas_hk_{account_no}_bill_due_date"

    @property
    def native_value(self) -> datetime.date | None:
        return self._coordinator.bill_due_date
