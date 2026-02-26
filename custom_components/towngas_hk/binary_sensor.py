"""Binary sensor platform for Hong Kong Towngas."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TownGasCoordinator, TownGasData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Towngas binary sensors using the shared coordinator."""
    coordinator: TownGasCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        TownGasOverdueSensor(coordinator),
        TownGasCurrentEstimateBinary(coordinator),
        TownGasNextEstimateBinary(coordinator),
    ])


class TownGasBaseBinary(CoordinatorEntity[TownGasCoordinator], BinarySensorEntity):
    """Base class for Towngas binary sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def _data(self) -> TownGasData:
        return self.coordinator.data


class TownGasOverdueSensor(TownGasBaseBinary):
    """Binary sensor: on when the account has an overdue bill."""

    _attr_name = "Overdue Bill"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_overdue"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_overdue if self.coordinator.data else False


class TownGasCurrentEstimateBinary(TownGasBaseBinary):
    """Binary sensor: on when current month consumption is an estimate."""

    _attr_translation_key = "current_consumption_is_estimate"
    _attr_icon = "mdi:help-circle-outline"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_current_consumption_is_estimate"

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_current_month_estimate)


class TownGasNextEstimateBinary(TownGasBaseBinary):
    """Binary sensor: on when next month consumption is an estimate."""

    _attr_translation_key = "next_consumption_is_estimate"
    _attr_icon = "mdi:help-circle-outline"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_next_consumption_is_estimate"

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_next_month_estimate)
