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
    _entity_id_suffix: str = ""

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        account = coordinator.account_no
        if self._entity_id_suffix:
            self.entity_id = f"binary_sensor.towngas_hk_{account}_{self._entity_id_suffix}"
            self._attr_unique_id = f"towngas_hk_{account}_{self._entity_id_suffix}"

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def _data(self) -> TownGasData:
        return self.coordinator.data


class TownGasOverdueSensor(TownGasBaseBinary):
    """Binary sensor: on when the account has an overdue bill."""

    _attr_translation_key = "overdue_bill"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle"
    _entity_id_suffix = "overdue"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_overdue if self.coordinator.data else False


class TownGasCurrentEstimateBinary(TownGasBaseBinary):
    """Binary sensor: on when current month consumption is an estimate."""

    _attr_translation_key = "current_month_usage_is_estimate"
    _attr_icon = "mdi:help-circle-outline"
    _entity_id_suffix = "current_month_usage_is_estimate"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_current_month_estimate)


class TownGasNextEstimateBinary(TownGasBaseBinary):
    """Binary sensor: on when next month consumption is an estimate."""

    _attr_translation_key = "next_month_usage_is_estimate"
    _attr_icon = "mdi:help-circle-outline"
    _entity_id_suffix = "next_month_usage_is_estimate"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        return bool(self._data.is_next_month_estimate)
