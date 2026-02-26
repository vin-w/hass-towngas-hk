"""Binary sensor platform for Hong Kong Towngas."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TownGasCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Towngas binary sensors using the shared coordinator."""
    coordinator: TownGasCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([TownGasOverdueSensor(coordinator)])


class TownGasOverdueSensor(CoordinatorEntity[TownGasCoordinator], BinarySensorEntity):
    """Binary sensor: on when the account has an overdue bill."""

    _attr_has_entity_name = True
    _attr_name = "Overdue Bill"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"towngas_hk_{coordinator.account_no}_overdue"

    @property
    def device_info(self):
        return self.coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_overdue if self.coordinator.data else False
