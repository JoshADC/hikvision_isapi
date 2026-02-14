"""Number platform for Hikvision ISAPI integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import EntityType
from .coordinator import HikvisionISAPICoordinator
from .entity import HikvisionISAPIEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hikvision ISAPI numbers from a config entry."""
    coordinator: HikvisionISAPICoordinator = entry.runtime_data

    entities = [
        HikvisionISAPINumber(coordinator, descriptor)
        for descriptor in coordinator.entity_descriptors
        if descriptor.entity_type == EntityType.NUMBER
    ]
    async_add_entities(entities)


class HikvisionISAPINumber(HikvisionISAPIEntity, NumberEntity):
    """A number entity for Hikvision ISAPI numeric settings."""

    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, descriptor):
        super().__init__(coordinator, descriptor)
        self._attr_native_min_value = descriptor.min_value or 0
        self._attr_native_max_value = descriptor.max_value or 100
        self._attr_native_step = 1.0

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        val = self._current_value
        if val:
            try:
                return float(val)
            except ValueError:
                return None
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value via ISAPI."""
        str_value = str(int(value))
        result = await self.coordinator.client.put_setting(
            self._descriptor.path, str_value
        )
        if result.success:
            # Optimistic update
            self.coordinator.data[self._descriptor.path] = str_value
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(
                "Failed to set %s=%s: %s",
                self._descriptor.path,
                str_value,
                result.sub_status,
            )
