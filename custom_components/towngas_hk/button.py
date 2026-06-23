"""Button platform for Hong Kong Towngas — force refresh."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TownGasCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TownGasCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([TownGasForceRefresh(coordinator)])


class TownGasForceRefresh(CoordinatorEntity[TownGasCoordinator], ButtonEntity):
    """Force a data refresh by clearing the next_refresh timer."""

    _attr_has_entity_name = True
    _attr_translation_key = "force_refresh"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: TownGasCoordinator) -> None:
        super().__init__(coordinator)
        account = coordinator.account_no
        self.entity_id = f"button.towngas_hk_{account}_force_refresh"
        self._attr_unique_id = f"towngas_hk_{account}_force_refresh"

    @property
    def device_info(self):
        return self.coordinator.device_info

    async def async_press(self) -> None:
        """Force refresh — clear timers so coordinator fetches fresh data."""
        self.coordinator._next_refresh = None
        self.coordinator._last_refresh = None
        self.coordinator._last_reauth_time = None
        self.coordinator._restored_data = None
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Towngas: force refresh requested for account %s", self.coordinator.account_no)
