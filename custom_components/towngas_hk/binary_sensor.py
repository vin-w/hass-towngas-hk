"""Binary sensor platform for Hong Kong Towngas."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ACCOUNT_NO
from .sensor import TownGasCoordinator, _device_info


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Towngas binary sensors from a config entry."""
    data = config_entry.data
    session = async_get_clientsession(hass)
    account_no = data[CONF_ACCOUNT_NO]

    coordinator = TownGasCoordinator(
        session,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        account_no,
    )

    async_add_entities(
        [TownGasOverdueSensor(coordinator, account_no)],
        update_before_add=True,
    )


class TownGasOverdueSensor(BinarySensorEntity):
    """Binary sensor: True when account has an overdue bill."""

    _attr_has_entity_name = True
    _attr_name = "Overdue Bill"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator: TownGasCoordinator, account_no: str) -> None:
        self._coordinator = coordinator
        self._account_no = account_no
        self._attr_unique_id = f"towngas_hk_{account_no}_overdue"

    @property
    def device_info(self) -> dict:
        return _device_info(self._account_no)

    @property
    def is_on(self) -> bool:
        return self._coordinator.is_overdue

    async def async_update(self) -> None:
        await self._coordinator.async_update()
