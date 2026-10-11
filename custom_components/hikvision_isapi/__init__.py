"""Hikvision ISAPI Image Control integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_LEGACY_SELECT_VALUES, CONF_NAME, DOMAIN, PLATFORMS
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
    coordinator.display_name = (
        entry.data.get(CONF_NAME) or f"{device_info.model} ({entry.data[CONF_HOST]})"
    )
    coordinator.legacy_select_values = entry.options.get(
        CONF_LEGACY_SELECT_VALUES, False
    )

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

    # Reload when the options change so selects rebuild with the new values
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries created by older versions.

    1.1 -> 1.2 (v1.4.0): select entities switched from English words to raw
    camera values. Cameras set up before that keep the English words so
    existing automations don't break; users can switch in the options.
    """
    if entry.version == 1 and entry.minor_version < 2:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_LEGACY_SELECT_VALUES: True},
            minor_version=2,
        )
        _LOGGER.info(
            "Migrated %s: keeping English dropdown values for existing automations",
            entry.title,
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: HikvisionISAPICoordinator = entry.runtime_data
        await coordinator.client.close()

    return unload_ok
