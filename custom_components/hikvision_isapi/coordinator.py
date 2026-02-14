"""DataUpdateCoordinator for Hikvision ISAPI integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .capabilities import EntityDescriptor, parse_capabilities, _build_value_map, _strip_ns
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .isapi_client import DeviceInfo, ISAPIClient

_LOGGER = logging.getLogger(__name__)


class HikvisionISAPICoordinator(DataUpdateCoordinator):
    """Coordinator that polls ISAPI for current image settings."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ISAPIClient,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_info.unique_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.device_info = device_info
        self.entity_descriptors: List[EntityDescriptor] = []
        self._capabilities_fetched = False

    async def _async_update_data(self) -> Dict[str, str]:
        """Fetch current values from the camera.

        On first run, also fetch capabilities to build entity descriptors.
        Returns a {path: value} dict of current settings.
        """
        try:
            if not self._capabilities_fetched:
                caps_xml = await self.client.get_capabilities()
                values_xml = await self.client.get_current_values()
                self.entity_descriptors = parse_capabilities(caps_xml, values_xml)
                self._capabilities_fetched = True
                return {e.path: e.current_value for e in self.entity_descriptors}

            values_xml = await self.client.get_current_values()
            value_map = _build_value_map(values_xml)

            # Update entity descriptors with fresh values
            for entity in self.entity_descriptors:
                if entity.path in value_map:
                    entity.current_value = value_map[entity.path]
                elif entity.linked_enabled_path is not None:
                    # Mode tag absent from XML — feature is disabled
                    enabled = value_map.get(entity.linked_enabled_path, "")
                    if enabled.lower() != "true" and entity.off_value:
                        entity.current_value = entity.off_value

            return value_map

        except Exception as err:
            raise UpdateFailed(f"Error communicating with camera: {err}") from err
