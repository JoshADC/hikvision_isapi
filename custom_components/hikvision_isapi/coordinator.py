"""DataUpdateCoordinator for Hikvision ISAPI integration."""

from __future__ import annotations

from datetime import timedelta
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .capabilities import EntityDescriptor, EntityType, parse_capabilities, _build_value_map, _strip_ns
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .isapi_client import DeviceInfo, ISAPIClient

import re

_LOGGER = logging.getLogger(__name__)

_PLATFORM_KEY = {
    EntityType.SWITCH: "switch",
    EntityType.NUMBER: "number",
    EntityType.SELECT: "select",
}

# Options that are purely digits or simple fractions (e.g. "4", "1/1000")
# read the same in every language - no "state" translation entry is needed
# for them, and flagging them would just be noise on every startup.
_NUMERIC_OPTION = re.compile(r"^\d+(/\d+)?$")


_GITHUB_ISSUES_URL = "https://github.com/JoshADC/hikvision_isapi/issues"


async def _check_translation_coverage(
    hass: HomeAssistant, device_info: DeviceInfo, entities: List[EntityDescriptor]
) -> None:
    """Log any entity/select-option missing from strings.json, in one message,
    and raise a Home Assistant Repairs issue so the gap is visible in the UI
    rather than only in the log.

    Different camera models can report the same logical setting under a
    different ISAPI path (a different translation_key), or expose select
    options nobody has seen before on this integration. Neither case
    breaks anything — Home Assistant just falls back to a generic name or
    the raw untranslated value — but that's easy to miss silently. This
    check surfaces every gap at once, the first time a given camera's
    capabilities are parsed, so it can be filled in.
    """
    issue_id = f"translation_gaps_{device_info.unique_id}"
    strings_path = Path(__file__).parent / "strings.json"
    try:
        # read_text() is blocking disk I/O - must not run directly on the
        # event loop (this is what util.loop's blocking-call detector was
        # correctly flagging). Offload it to the executor instead.
        raw = await hass.async_add_executor_job(strings_path.read_text)
        strings = json.loads(raw)
    except (OSError, json.JSONDecodeError) as err:
        _LOGGER.debug("Translation coverage check skipped: %s", err)
        return

    entity_strings = strings.get("entity", {})
    issues: list[str] = []

    for e in entities:
        platform = _PLATFORM_KEY.get(e.entity_type)
        entry = entity_strings.get(platform, {}).get(e.translation_key)

        if entry is None:
            issues.append(
                f"- {e.path}  (translation_key: {e.translation_key})  "
                f"→ no entry under entity.{platform}.{e.translation_key} "
                f"in strings.json; will display a generic fallback name"
            )
            continue

        if e.entity_type == EntityType.SELECT:
            state = entry.get("state", {})
            untranslated = [
                o for o in e.options
                if o not in state and not _NUMERIC_OPTION.match(o)
            ]
            if untranslated:
                issues.append(
                    f"- {e.path}  (translation_key: {e.translation_key})  "
                    f"→ untranslated option(s): {', '.join(untranslated)}"
                )

    if issues:
        summary = "\n".join(issues)
        _LOGGER.warning(
            "Translation coverage gaps for %s (firmware %s): harmless - "
            "raw values are shown until these are added to strings.json / "
            "translations/en.json\n%s",
            device_info.model,
            device_info.firmware_version,
            summary,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="translation_gaps",
            translation_placeholders={
                "count": str(len(issues)),
                "model": device_info.model,
                "gaps": summary,
                "firmware": device_info.firmware_version,
                "github_url": _GITHUB_ISSUES_URL,
            },
            learn_more_url=_GITHUB_ISSUES_URL,
        )
    else:
        # No gaps found (or the last-known gaps have since been fixed) -
        # clear any previously-raised issue for this camera. Safe to call
        # even if none exists.
        ir.async_delete_issue(hass, DOMAIN, issue_id)


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
                await _check_translation_coverage(
                    self.hass, self.device_info, self.entity_descriptors
                )
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
