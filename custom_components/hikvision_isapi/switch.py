"""Switch platform for Hikvision ISAPI integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import EntityType
from .coordinator import HikvisionISAPICoordinator
from .entity import HikvisionISAPIEntity
from .prerequisites import put_with_prerequisites

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hikvision ISAPI switches from a config entry."""
    coordinator: HikvisionISAPICoordinator = entry.runtime_data

    entities = [
        HikvisionISAPISwitch(coordinator, descriptor)
        for descriptor in coordinator.entity_descriptors
        if descriptor.entity_type == EntityType.SWITCH
    ]
    async_add_entities(entities)


class HikvisionISAPISwitch(HikvisionISAPIEntity, SwitchEntity):
    """A switch entity for Hikvision ISAPI boolean settings."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._current_value.lower() == "true"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_value("true")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_value("false")

    async def _set_value(self, value: str) -> None:
        """Set the switch value via ISAPI."""
        result = await put_with_prerequisites(
            self.coordinator.client,
            self._descriptor.path,
            value,
        )
        if result.success:
            # Optimistic update
            self.coordinator.data[self._descriptor.path] = value
            self.async_write_ha_state()
            # Refresh coordinator to pick up any side effects
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(
                "Failed to set %s=%s: %s",
                self._descriptor.path,
                value,
                result.sub_status,
            )
