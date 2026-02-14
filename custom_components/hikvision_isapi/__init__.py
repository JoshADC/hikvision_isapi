"""Hikvision ISAPI Image Control integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import HikvisionISAPICoordinator
from .isapi_client import ISAPIClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hikvision ISAPI from a config entry."""
    client = ISAPIClient(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    # Validate connection and get device info
    device_info = await client.get_device_info()

    coordinator = HikvisionISAPICoordinator(hass, client, device_info)

    # First refresh fetches capabilities + current values and builds entity descriptors
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info(
        "Connected to %s (%s) — %d entities discovered",
        device_info.model,
        entry.data[CONF_HOST],
        len(coordinator.entity_descriptors),
    )

    # Store coordinator on the entry for platform access
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: HikvisionISAPICoordinator = entry.runtime_data
        await coordinator.client.close()

    return unload_ok
