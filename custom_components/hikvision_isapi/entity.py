"""Base entity for Hikvision ISAPI integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo as HADeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capabilities import EntityDescriptor
from .const import DOMAIN
from .coordinator import HikvisionISAPICoordinator


class HikvisionISAPIEntity(CoordinatorEntity[HikvisionISAPICoordinator]):
    """Base class for Hikvision ISAPI entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HikvisionISAPICoordinator,
        descriptor: EntityDescriptor,
    ) -> None:
        super().__init__(coordinator)
        self._descriptor = descriptor
        device = coordinator.device_info

        # Unique ID: MAC + ISAPI path (unchanged — do not alter existing unique_ids)
        self._attr_unique_id = f"{device.unique_id}_{descriptor.path}"
        self._attr_translation_key = descriptor.translation_key
        # Deliberately NOT setting self._attr_name here (not even to None).
        # HA's Entity.name property returns _attr_name immediately if the
        # attribute exists at all, regardless of its value — so assigning
        # None skips the translation_key lookup entirely instead of
        # triggering it. Leaving the attribute unset is what lets `name`
        # fall through to UNDEFINED, which is what makes HA look up the
        # translation via translation_key + has_entity_name.

    @property
    def device_info(self) -> HADeviceInfo:
        """Return device info for the device registry."""
        device = self.coordinator.device_info
        return HADeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=f"{device.model} ({self.coordinator.client.host})",
            manufacturer="Hikvision",
            model=device.model,
            sw_version=f"{device.firmware_version} {device.firmware_build}",
            serial_number=device.serial_number,
        )

    @property
    def _current_value(self) -> str:
        """Get the current value for this entity from coordinator data."""
        if self.coordinator.data and self._descriptor.path in self.coordinator.data:
            return self.coordinator.data[self._descriptor.path]
        return self._descriptor.current_value
