"""Select platform for Hikvision ISAPI integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import FRIENDLY_NAMES, EntityType
from .coordinator import HikvisionISAPICoordinator
from .entity import HikvisionISAPIEntity
from .prerequisites import put_with_prerequisites

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hikvision ISAPI selects from a config entry."""
    coordinator: HikvisionISAPICoordinator = entry.runtime_data

    entities = [
        HikvisionISAPISelect(coordinator, descriptor)
        for descriptor in coordinator.entity_descriptors
        if descriptor.entity_type == EntityType.SELECT
    ]
    async_add_entities(entities)


class HikvisionISAPISelect(HikvisionISAPIEntity, SelectEntity):
    """A select entity for Hikvision ISAPI dropdown settings."""

    _entity_description_class = SelectEntityDescription

    def __init__(self, coordinator, descriptor):
        super().__init__(coordinator, descriptor)
        # Options are raw ISAPI values. HA translates them for display in the
        # picker using this entity's translation_key + the "state" block in
        # strings.json/translations/<lang>.json — see entity.py for the key.
        #
        # Legacy mode (cameras set up before v1.4.0) keeps the old English
        # words as the values so existing automations keep working. Those
        # words have no "state" translation, so HA shows them as-is.
        if coordinator.legacy_select_values:
            friendly = [FRIENDLY_NAMES.get(o, o) for o in descriptor.options]
            self._raw_to_shown = dict(zip(descriptor.options, friendly))
            self._shown_to_raw = dict(zip(friendly, descriptor.options))
            self._attr_options = friendly
        else:
            self._raw_to_shown = {}
            self._shown_to_raw = {}
            self._attr_options = descriptor.options
        # For merged mode selects (e.g., BLC Mode controls both mode and enabled)
        self._linked_enabled_path = descriptor.linked_enabled_path
        self._off_value = descriptor.off_value

    @property
    def current_option(self) -> str | None:
        """Return the current selected option (raw ISAPI value)."""
        raw = self._current_value
        # For linked selects, the enabled flag is the source of truth for
        # whether the feature is on or off.  The mode tag disappears from
        # the camera XML when the feature is disabled, so `raw` may hold a
        # stale non-off value from the descriptor fallback.
        if self._linked_enabled_path:
            enabled = self.coordinator.data.get(
                self._linked_enabled_path, ""
            )
            if enabled.lower() != "true":
                raw = self._off_value
        return self._raw_to_shown.get(raw, raw) if raw else None

    async def async_select_option(self, option: str) -> None:
        """Select an option via ISAPI."""
        raw_value = self._shown_to_raw.get(option, option)

        if self._linked_enabled_path:
            result = await self._set_linked_mode(raw_value)
        else:
            result = await put_with_prerequisites(
                self.coordinator.client,
                self._descriptor.path,
                raw_value,
            )

        if result.success:
            # Optimistic update
            self.coordinator.data[self._descriptor.path] = raw_value
            if self._linked_enabled_path:
                self.coordinator.data[self._linked_enabled_path] = (
                    "false" if raw_value == self._off_value else "true"
                )
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(
                "Failed to set %s=%s: %s",
                self._descriptor.path,
                raw_value,
                result.error_description,
            )

    async def _set_linked_mode(self, raw_value: str):
        """Handle a mode select that also controls an enabled boolean.

        Uses the prerequisite engine to auto-resolve conflicts (e.g.,
        enabling BLC while WDR is on → auto-disable WDR first).
        """
        from .prerequisites import CONFLICT_RESOLUTIONS

        if raw_value == self._off_value:
            # Turning off: disable and set mode to off value in one PUT
            return await self.coordinator.client.put_settings({
                self._linked_enabled_path: "false",
                self._descriptor.path: raw_value,
            })

        # Turning on: set enabled=true AND set/insert the mode
        result = await self.coordinator.client.put_setting_with_enable(
            self._linked_enabled_path,
            self._descriptor.path,
            raw_value,
        )

        if result.success:
            return result

        # Check for known conflicts and auto-resolve
        resolution = CONFLICT_RESOLUTIONS.get(result.sub_status)
        if resolution is None:
            return result

        _LOGGER.info(
            "Conflict detected (%s) — disabling %s then enabling %s=%s",
            result.sub_status,
            resolution,
            self._descriptor.path,
            raw_value,
        )

        # Step 1: Disable the blocker
        prereq_result = await self.coordinator.client.put_settings(resolution)
        if not prereq_result.success:
            return prereq_result

        # Step 2: Retry the enable + mode set
        return await self.coordinator.client.put_setting_with_enable(
            self._linked_enabled_path,
            self._descriptor.path,
            raw_value,
        )
