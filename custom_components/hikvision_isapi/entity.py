"""Base entity for Hikvision ISAPI integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo as HADeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capabilities import EntityDescriptor
from .const import DOMAIN
from .coordinator import HikvisionISAPICoordinator


class HikvisionISAPIEntity(CoordinatorEntity[HikvisionISAPICoordinator]):
    """Base class for Hikvision ISAPI entities."""

    _attr_has_entity_name = True

    # Each platform module's own entity class must override this with its
    # matching *EntityDescription subclass (e.g. NumberEntityDescription).
    # HA's NumberEntity/SwitchEntity/SelectEntity property implementations
    # assume entity_description, when set, is their own subclass - reading
    # a field like native_unit_of_measurement straight off it without
    # checking. A bare EntityDescription doesn't have those fields and
    # raises AttributeError the moment such a property is read (which HA
    # does for every entity as soon as it's added).
    _entity_description_class: type[EntityDescription] = EntityDescription

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
        # Deliberately NOT setting self._attr_name (not even to None): HA's
        # Entity.name property returns _attr_name immediately if the
        # attribute exists at all, which would skip the translation_key
        # lookup below entirely - even the entity_description fallback
        # further down would never be reached.
        #
        # entity_description.name is HA's built-in fallback: when
        # translation_key has no matching entry in any loaded strings.json
        # (an untested camera model reporting a path we don't recognize),
        # HA falls back to this instead of showing no name at all.
        # descriptor.name (ENTITY_NAMES lookup, or a generated name as a
        # last resort) is exactly that fallback - only used when no
        # translation is found; a real translation always takes priority.
        self.entity_description = self._entity_description_class(
            key=descriptor.translation_key,
            name=descriptor.name,
        )

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
