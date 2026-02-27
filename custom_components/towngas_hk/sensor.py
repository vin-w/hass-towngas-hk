"""Sensor platform for Hong Kong Towngas.

Sensors are named using authentic HK billing terminology: 用量 (MJ) and
度數 (meter units). Old IDs have been retired; there is no backward
compatibility. New unique_ids follow `towngas_<account>_<suffix>`.
"""

from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TownGasCoordinator, TownGasData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TownGasCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        # usage sensors (MJ)
        TownGasCurrentMonthUsageMJSensor(coordinator),
        TownGasNextMonthEstimateMJSensor(coordinator),
        # unit sensors (display only)
        TownGasCurrentMonthUsageUnitSensor(coordinator),
        TownGasNextMonthEstimateUnitSensor(coordinator),
        # existing metadata sensors
        TownGasCurrentMonthCodeSensor(coordinator),
        TownGasNextMonthCodeSensor(coordinator),
        TownGasAccountSensor(coordinator),
        TownGasBalanceSensor(coordinator),
        TownGasBillAmountSensor(coordinator),
        TownGasBillDateSensor(coordinator),
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


class TownGasCurrentMonthUsageMJSensor(TownGasBaseSensor):
    """Actual gas usage for the current month in megajoules (MJ).

    The value corresponds to the last completed meter read. The sensor exposes
    `month` and `is_estimate` attributes for dashboard templates.
    """

    _attr_translation_key = "current_month_usage_mj"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fire"
    _entity_id_suffix = "current_usage_mj"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> float | None:
        return self._data.current_month_consumption

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "month": self._data.current_month,
            "is_estimate": self._data.is_current_month_estimate,
        }




class TownGasNextMonthEstimateMJSensor(TownGasBaseSensor):
    """Projected gas usage for the upcoming month in MJ.

    This is a rolling estimate until the next meter read; on 2026/02/27 the
    estimate might be 24 MJ for March (partial cycle).
    """

    _attr_translation_key = "next_month_estimate_mj"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fire"
    _entity_id_suffix = "next_estimate_mj"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> float | None:
        return self._data.next_month_consumption

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "month": self._data.next_month,
            "is_estimate": self._data.is_next_month_estimate,
        }


# ---------------------------------------------------------------------------
# Unit sensors – display only, no energy/device class
# ---------------------------------------------------------------------------

class TownGasCurrentMonthUsageUnitSensor(TownGasCurrentMonthUsageMJSensor):
    _attr_translation_key = "current_month_usage_unit"
    _attr_native_unit_of_measurement = "Unit"
    _entity_id_suffix = "current_usage_unit"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> int | None:  # type: ignore[override]
        val = super().native_value
        return int(val / 48) if val is not None else None


class TownGasNextMonthEstimateUnitSensor(TownGasNextMonthEstimateMJSensor):
    _attr_translation_key = "next_month_estimate_unit"
    _attr_native_unit_of_measurement = "Unit"
    _entity_id_suffix = "next_estimate_unit"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> int | None:  # type: ignore[override]
        val = super().native_value
        return int(val / 48) if val is not None else None


class TownGasAccountSensor(TownGasBaseSensor):
    _attr_translation_key = "account_no"
    _attr_icon = "mdi:account"
    _entity_id_suffix = "account_no"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> str | None:
        # Expose the Towngas account number as a dedicated sensor
        return self.coordinator.account_no


class TownGasBalanceSensor(TownGasBaseSensor):
    _attr_translation_key = "current_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"
    _entity_id_suffix = "balance"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


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


class TownGasBillAmountSensor(TownGasBaseSensor):
    _attr_translation_key = "bill_amount_due"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "HKD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:receipt"
    _entity_id_suffix = "bill_amount"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> float | None:
        return self._data.bill_amount_due


class TownGasBillDateSensor(TownGasBaseSensor):
    _attr_translation_key = "bill_due_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"
    _entity_id_suffix = "bill_due_date"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> datetime.date | None:
        return self._data.bill_due_date


# ---- additional sensors --------------------------------------------------

class TownGasCurrentMonthCodeSensor(TownGasBaseSensor):
    _attr_translation_key = "current_month_code"
    _attr_icon = "mdi:calendar"
    _entity_id_suffix = "current_month_code"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> str | None:
        """Return a machine-friendly month code like 'YYYY-MM'."""
        month_str = self._data.current_month
        if not month_str:
            return None
        try:
            dt = datetime.datetime.strptime(month_str, "%b %Y")
            return dt.strftime("%Y-%m")
        except ValueError:
            return None


class TownGasNextMonthCodeSensor(TownGasBaseSensor):
    _attr_translation_key = "next_month_code"
    _attr_icon = "mdi:calendar"
    _entity_id_suffix = "next_month_code"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)


    @property
    def native_value(self) -> str | None:
        """Return a machine-friendly month code like 'YYYY-MM'."""
        month_str = self._data.next_month
        if not month_str:
            return None
        try:
            dt = datetime.datetime.strptime(month_str, "%b %Y")
            return dt.strftime("%Y-%m")
        except ValueError:
            return None


