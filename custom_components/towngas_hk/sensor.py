"""Sensor platform for Hong Kong Towngas."""

from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity
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
        TownGasCurrentConsumptionSensor(coordinator),
        TownGasNextConsumptionSensor(coordinator),
        # unit-based copies (1 unit = 48 MJ, integer)
        TownGasCurrentConsumptionUnitSensor(coordinator),
        TownGasNextConsumptionUnitSensor(coordinator),
        TownGasCurrentMonthCodeSensor(coordinator),
        TownGasNextMonthCodeSensor(coordinator),
        TownGasAccountSensor(coordinator),
        TownGasBalanceSensor(coordinator),
        TownGasBillAmountSensor(coordinator),
        TownGasBillDateSensor(coordinator),
        TownGasCurrentEstimateBinary(coordinator),
        TownGasNextEstimateBinary(coordinator),
    ])


class TownGasBaseSensor(CoordinatorEntity[TownGasCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def _data(self) -> TownGasData:
        return self.coordinator.data


class TownGasBaseBinary(CoordinatorEntity[TownGasCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def _data(self) -> TownGasData:
        return self.coordinator.data


class TownGasCurrentConsumptionSensor(TownGasBaseSensor):
    _attr_translation_key = "current_month_gas_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_current_consumption"

    @property
    def native_value(self) -> float | None:
        return self._data.current_month_consumption

    @property
    def extra_state_attributes(self) -> dict:
        # Expose a minimal, consistent attribute set for templates and the
        # Energy dashboard: `month` and `is_estimate`.
        return {
            "month": self._data.current_month,
            "is_estimate": self._data.is_current_month_estimate,
        }




class TownGasNextConsumptionSensor(TownGasBaseSensor):
    _attr_translation_key = "next_month_gas_consumption"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "MJ"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:fire"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_next_consumption"

    @property
    def native_value(self) -> float | None:
        return self._data.next_month_consumption

    @property
    def extra_state_attributes(self) -> dict:
        # Minimal consistent attributes for next-month sensor as well
        return {
            "month": self._data.next_month,
            "is_estimate": self._data.is_next_month_estimate,
        }


# ---------------------------------------------------------------------------
# Unit-conversion sensors (1 unit = 48 MJ)
# ---------------------------------------------------------------------------

class TownGasCurrentConsumptionUnitSensor(TownGasCurrentConsumptionSensor):
    _attr_translation_key = "current_month_gas_consumption_unit"
    _attr_native_unit_of_measurement = "Unit"

    def native_value(self) -> int | None:  # type: ignore[override]
        val = super().native_value
        return int(val / 48) if val is not None else None


class TownGasNextConsumptionUnitSensor(TownGasNextConsumptionSensor):
    _attr_translation_key = "next_month_gas_consumption_unit"
    _attr_native_unit_of_measurement = "Unit"

    def native_value(self) -> int | None:  # type: ignore[override]
        val = super().native_value
        return int(val / 48) if val is not None else None


class TownGasAccountSensor(TownGasBaseSensor):
    _attr_translation_key = "account_no"
    _attr_icon = "mdi:account"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_account_no"

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

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_balance"

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

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_bill_amount"

    @property
    def native_value(self) -> float | None:
        return self._data.bill_amount_due


class TownGasBillDateSensor(TownGasBaseSensor):
    _attr_translation_key = "bill_due_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_bill_due_date"

    @property
    def native_value(self) -> datetime.date | None:
        return self._data.bill_due_date


# ---- additional sensors --------------------------------------------------

class TownGasCurrentMonthCodeSensor(TownGasBaseSensor):
    _attr_translation_key = "current_month_code"
    _attr_icon = "mdi:calendar"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_current_month_code"

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

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_next_month_code"

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


class TownGasCurrentEstimateBinary(TownGasBaseBinary):
    _attr_translation_key = "current_is_estimate"
    _attr_icon = "mdi:help-circle-outline"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_current_is_estimate"

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_current_month_estimate)


class TownGasNextEstimateBinary(TownGasBaseBinary):
    _attr_translation_key = "next_is_estimate"
    _attr_icon = "mdi:help-circle-outline"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_next_is_estimate"

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_next_month_estimate)
