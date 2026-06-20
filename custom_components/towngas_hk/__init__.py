"""Hong Kong Towngas integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ACCOUNT_NO, DEFAULT_FUEL_ADJUSTMENT_RATE, DOMAIN, FUEL_RATE_ENTITY
from .coordinator import TownGasCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Towngas from a config entry — create one shared coordinator."""
    coordinator = TownGasCoordinator(
        hass=hass,
        session=async_get_clientsession(hass),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        account_no=entry.data[CONF_ACCOUNT_NO],
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    # create a helper entity for the fuel adjustment rate (text input)
    account_no = entry.data[CONF_ACCOUNT_NO]
    rate_entity = FUEL_RATE_ENTITY.format(account=account_no)
    # only create if it doesn't already exist (idempotent)
    if hass.states.get(rate_entity) is None:
        await hass.services.async_call(
            "input_number",
            "create",
            {
                "name": f"Towngas {account_no} Fuel Adjust Rate",
                "icon": "mdi:calculator",
                "min": 0,
                "max": 100,
                "step": 0.01,
                "mode": "box",
                "unit_of_measurement": "¢/MJ",
                "initial": DEFAULT_FUEL_ADJUSTMENT_RATE,
                "entity_id": rate_entity,
            },
            blocking=True,
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
