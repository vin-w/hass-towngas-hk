"""Sensor platform for Hong Kong Towngas.

Sensors are named using authentic HK billing terminology: 用量 (MJ) and
度數 (meter units). Entity unique_ids follow `towngas_<account>_<suffix>`.
"""

from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BASIC_CHARGE,
    DEFAULT_FUEL_ADJUSTMENT_RATE,
    FUEL_RATE_ENTITY,
    MAINTENANCE_FEE,
    TARIFF_TIERS,
)
from .coordinator import TownGasCoordinator, TownGasData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TownGasCoordinator = hass.data["towngas_hk"][config_entry.entry_id]
    async_add_entities([
        # consumption sensors
        TownGasConsumptionMj(coordinator),
        TownGasConsumptionUnits(coordinator),
        TownGasMeterReading(coordinator),
        # reading metadata
        TownGasReadingType(coordinator),
        TownGasReadingDate(coordinator),
        TownGasLatestReadingText(coordinator),
        # tariff
        TownGasTariffEstimate(coordinator),
        # account / billing
        TownGasAccountNo(coordinator),
        TownGasBalance(coordinator),
        TownGasBillAmount(coordinator),
        TownGasBillDueDate(coordinator),
    ])


class TownGasBaseSensor(CoordinatorEntity[TownGasCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _entity_id_suffix: str = ""

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        account = coordinator.account_no
        if self._entity_id_suffix:
            self.entity_id = f"sensor.towngas_hk_{account}_{self._entity_id_suffix}"
            self._attr_unique_id = f"towngas_hk_{account}_{self._entity_id_suffix}"

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def _data(self) -> TownGasData:
        return self.coordinator.data


# ---------------------------------------------------------------------------
# Consumption sensors
# ---------------------------------------------------------------------------

class TownGasConsumptionMj(TownGasBaseSensor):
    """Monthly gas consumption in megajoules (MJ).

    Value = historyList[0].consumption × 48.
    This is the actual billed consumption for the most recent meter reading.
    """

    _attr_translation_key = "consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fire"
    _entity_id_suffix = "consumption"

    @property
    def native_value(self) -> float | None:
        return self._data.latest_consumption_mj

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "reading_type": self._data.latest_reading_type,
            "reading_date": self._data.latest_reading_date.isoformat()
            if self._data.latest_reading_date
            else None,
            "meter_reading": self._data.latest_meter_reading,
            "consumption_units": self._data.latest_consumption_units,
            "has_prediction": self._data.is_show_prediction,
            "latest_reading_text": self._data.latest_reading_text,
        }


class TownGasConsumptionUnits(TownGasBaseSensor):
    """Monthly gas consumption in meter units (度數).

    Value = historyList[0].consumption (raw units from API).
    """

    _attr_translation_key = "consumption_units"
    _attr_native_unit_of_measurement = "units"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:counter"
    _entity_id_suffix = "consumption_units"

    @property
    def native_value(self) -> int | None:
        return self._data.latest_consumption_units


class TownGasMeterReading(TownGasBaseSensor):
    """Cumulative meter reading in units.

    This is an odometer-style value that only increases.
    """

    _attr_translation_key = "meter_reading"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:meter-gas"
    _entity_id_suffix = "meter_reading"

    @property
    def native_value(self) -> int | None:
        return self._data.latest_meter_reading


# ---------------------------------------------------------------------------
# Reading metadata sensors
# ---------------------------------------------------------------------------

class TownGasReadingType(TownGasBaseSensor):
    """How the latest reading was obtained: Remote, Actual, or Estimate."""

    _attr_translation_key = "reading_type"
    _attr_icon = "mdi:tag"
    _entity_id_suffix = "reading_type"

    @property
    def native_value(self) -> str | None:
        return self._data.latest_reading_type or None


class TownGasReadingDate(TownGasBaseSensor):
    """Date when the latest meter reading was taken."""

    _attr_translation_key = "reading_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar"
    _entity_id_suffix = "reading_date"

    @property
    def native_value(self) -> datetime.date | None:
        return self._data.latest_reading_date


class TownGasLatestReadingText(TownGasBaseSensor):
    """Pre-formatted latest reading text from Towngas API.

    Only available when isShowLatestMeterReading is true.
    """

    _attr_translation_key = "latest_reading_text"
    _attr_icon = "mdi:text"
    _entity_id_suffix = "latest_reading_text"

    @property
    def native_value(self) -> str | None:
        if not self._data.is_show_latest_reading:
            return None
        return self._data.latest_reading_text


# ---------------------------------------------------------------------------
# Tariff sensor
# ---------------------------------------------------------------------------

def calc_towngas_bill(mj: float, fuel_rate_cent: float) -> float:
    """Return total bill amount in HKD for the given usage and fuel rate.

    Based on Towngas tariff effective since 1 August 2024:
    https://www.towngas.com/en/Household/Customer-Services/Tariff

    Components:
    1. Gas charge – tiered pricing per MJ (TARIFF_TIERS in const.py)
    2. Fuel cost adjustment – variable rate × consumption MJ
    3. Monthly maintenance charge – HK$10
    4. Monthly initial charge – HK$20 (only if gas charge < $20)
    """
    remaining = mj
    gas_charge = 0.0
    for tier_mj, price_cent in TARIFF_TIERS:
        if remaining <= 0:
            break
        use_mj = min(remaining, tier_mj)
        gas_charge += use_mj * (price_cent / 100.0)
        remaining -= use_mj

    fuel_adj = mj * (fuel_rate_cent / 100.0)
    total = gas_charge + fuel_adj + MAINTENANCE_FEE

    # Monthly initial charge: levied if gas charge < $20
    if gas_charge < BASIC_CHARGE:
        total += BASIC_CHARGE

    return round(total, 2)


class TownGasTariffEstimate(TownGasBaseSensor):
    """Estimated bill based on latest monthly consumption.

    Uses the current fuel adjustment rate from input_number helper.
    """

    _attr_translation_key = "tariff_estimate"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"
    _entity_id_suffix = "tariff_estimate"

    @property
    def native_value(self) -> float | None:
        mj = self._data.latest_consumption_mj
        if mj is None:
            return None

        rate = DEFAULT_FUEL_ADJUSTMENT_RATE
        rate_entity = FUEL_RATE_ENTITY.format(account=self.coordinator.account_no)
        state = self.hass.states.get(rate_entity)
        if state is not None:
            try:
                rate = float(state.state)
            except (ValueError, TypeError):
                pass

        return calc_towngas_bill(mj, rate)

    @property
    def extra_state_attributes(self) -> dict:
        mj = self._data.latest_consumption_mj or 0

        rate = DEFAULT_FUEL_ADJUSTMENT_RATE
        rate_entity = FUEL_RATE_ENTITY.format(account=self.coordinator.account_no)
        state = self.hass.states.get(rate_entity)
        if state is not None:
            try:
                rate = float(state.state)
            except (ValueError, TypeError):
                pass

        return {
            "consumption_mj": mj,
            "fuel_rate_cents": rate,
            "tariff_source": "https://www.towngas.com/en/Household/Customer-Services/Tariff",
            "tariff_effective_date": "2024-08-01",
        }


# ---------------------------------------------------------------------------
# Account / billing sensors
# ---------------------------------------------------------------------------

class TownGasAccountNo(TownGasBaseSensor):
    _attr_translation_key = "account_no"
    _attr_icon = "mdi:account"
    _entity_id_suffix = "account_no"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.account_no


class TownGasBalance(TownGasBaseSensor):
    _attr_translation_key = "balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"
    _entity_id_suffix = "balance"

    @property
    def native_value(self) -> float | None:
        return self._data.current_balance

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "updated_date": self._data.balance_updated,
            "auto_pay": self._data.is_auto_pay,
            "ibill": self._data.is_ibill,
            "account_status": self._data.account_status,
        }


class TownGasBillAmount(TownGasBaseSensor):
    _attr_translation_key = "bill_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:receipt"
    _entity_id_suffix = "bill_amount"

    @property
    def native_value(self) -> float | None:
        return self._data.bill_amount_due


class TownGasBillDueDate(TownGasBaseSensor):
    _attr_translation_key = "bill_due_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"
    _entity_id_suffix = "bill_due_date"

    @property
    def native_value(self) -> datetime.date | None:
        return self._data.bill_due_date
