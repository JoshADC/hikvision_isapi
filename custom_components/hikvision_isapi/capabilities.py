"""Parse Hikvision ISAPI capabilities XML into entity descriptors.

The capabilities XML is self-describing:
  - opt="a,b,c"           → select entity (dropdown)
  - opt="true,false"      → switch entity (toggle)
  - min="0" max="100"     → number entity (slider)
  - opt="true"            → switch entity (always on, read-only indicator)
  - Single opt value      → skip or expose as read-only (e.g., ExposureType="manual" only)

Nested XML paths are flattened with "/" separators for entity addressing:
  e.g., Exposure/OverexposeSuppress/enabled
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

ISAPI_NS = "http://www.hikvision.com/ver20/XMLSchema"

# Human-readable names for Hikvision ISAPI values
FRIENDLY_NAMES: dict[str, str] = {
    # On/Off conventions
    "open": "On",
    "close": "Off",
    # Noise reduction
    "general": "Normal",
    # Supplement light
    "colorVuWhiteLight": "White Light",
    "irLight": "IR",
    # White balance
    "auto1": "Auto 1",
    "auto2": "Auto 2",
    "daylightLamp": "Fluorescent",
    "incandescentlight": "Incandescent",
    "warmlight": "Warm Light",
    "naturallight": "Natural Light",
    # Exposure / iris
    "pIris-General": "P-Iris",
    # Power line
    "50hz": "50 Hz",
    "60hz": "60 Hz",
    # Focus
    "SEMIAUTOMATIC": "Semi-automatic",
    "AUTO": "Auto",
    "MANUAL": "Manual",
    # BLC modes
    "CLOSE": "Off",
    "LEFTRIGHT": "Left-Right",
    "UPDOWN": "Up-Down",
    "CENTER": "Center",
    "Region": "Region",
    "AUTO": "Auto",
    # Generic
    "true": "On",
    "false": "Off",
    "manual": "Manual",
    "auto": "Auto",
    "locked": "Locked",
    "advanced": "Advanced",
    "day": "Day",
    "night": "Night",
    "schedule": "Schedule",
    "outdoor": "Outdoor",
    "indoor": "Indoor",
}

# Human-readable entity names for known ISAPI paths
ENTITY_NAMES: dict[str, str] = {
    "WDR/mode": "WDR",
    "WDR/WDRLevel": "WDR Level",
    "BLC/enabled": "BLC",
    "BLC/BLCMode": "BLC Mode",
    "HLC/enabled": "HLC",
    "HLC/HLCLevel": "HLC Level",
    "IrcutFilter/IrcutFilterType": "Day/Night Mode",
    "IrcutFilter/nightToDayFilterLevel": "Night-to-Day Sensitivity",
    "IrcutFilter/nightToDayFilterTime": "Night-to-Day Delay",
    "Exposure/ExposureType": "Iris Mode",
    "Exposure/autoIrisLevel": "Auto Iris Level",
    "Exposure/OverexposeSuppress/enabled": "Smart Supplement Light",
    "Exposure/pIris/pIrisType": "P-Iris Mode",
    "Exposure/pIris/IrisLevel": "P-Iris Level",
    "Shutter/ShutterLevel": "Shutter Speed",
    "Gain/GainLevel": "Gain",
    "Color/brightnessLevel": "Brightness",
    "Color/contrastLevel": "Contrast",
    "Color/saturationLevel": "Saturation",
    "Color/grayScale/grayScaleMode": "Color Space",
    "Sharpness/SharpnessLevel": "Sharpness",
    "NoiseReduce/mode": "Noise Reduction",
    "NoiseReduce/GeneralMode/generalLevel": "Noise Reduction Level",
    "NoiseReduce/AdvancedMode/FrameNoiseReduceLevel": "Spatial NR Level",
    "NoiseReduce/AdvancedMode/InterFrameNoiseReduceLevel": "Temporal NR Level",
    "Dehaze/DehazeMode": "Defog",
    "Dehaze/DehazeLevel": "Defog Level",
    "WhiteBalance/WhiteBalanceStyle": "White Balance",
    "WhiteBalance/WhiteBalanceRed": "White Balance Red",
    "WhiteBalance/WhiteBalanceBlue": "White Balance Blue",
    "ImageFlip/enabled": "Image Flip",
    "ImageFlip/ImageFlipStyle": "Flip Direction",
    "powerLineFrequency/powerLineFrequencyMode": "Power Line Frequency",
    "SupplementLight/supplementLightMode": "Supplement Light",
    "SupplementLight/whiteLightBrightness": "Light Brightness",
    "SupplementLight/highIrLightBrightness": "IR High Brightness",
    "SupplementLight/lowIrLightBrightness": "IR Low Brightness",
    "SupplementLight/mixedLightBrightnessRegulatMode": "Light Brightness Mode",
    "Scene/mode": "Scene Mode",
    "FocusConfiguration/focusStyle": "Focus Mode",
    "LensDistortionCorrection/enabled": "Lens Distortion Correction",
    "LensDistortionCorrection/accurateLevel": "Correction Level",
}

# Paths to skip — not useful as entities
SKIP_PATHS = {
    "id",
    "enabled",  # top-level channel enabled
    "videoInputID",
    "corridor/enabled",
    "PTZ/enabled",
    "SupplementLight/isAutoModeBrightnessCfg",
    "isSupportLaserSpotManual",
    "isSupportDOFAdjust",
    "isSupportAntiBandingParams",
}


class EntityType(Enum):
    SWITCH = "switch"
    NUMBER = "number"
    SELECT = "select"


@dataclass
class EntityDescriptor:
    path: str  # e.g., "Exposure/OverexposeSuppress/enabled"
    name: str  # e.g., "Smart Supplement Light"
    entity_type: EntityType
    options: list[str] = field(default_factory=list)  # raw ISAPI values for selects
    friendly_options: list[str] = field(default_factory=list)  # translated for UI
    min_value: float | None = None
    max_value: float | None = None
    current_value: str = ""
    # For merged mode selects (e.g., BLC): path to the enabled boolean
    # When set, this select controls both the mode and the enabled flag
    linked_enabled_path: str | None = None
    off_value: str | None = None  # Raw value meaning "off" (e.g., "CLOSE")

    def __str__(self) -> str:
        if self.entity_type == EntityType.SELECT:
            opts = ", ".join(
                f"{f} ({r})" if f != r else r
                for r, f in zip(self.options, self.friendly_options)
            )
            return f"[select]  {self.name:<30} = {self.friendly_value:<15} opts: {opts}"
        elif self.entity_type == EntityType.NUMBER:
            return (
                f"[number]  {self.name:<30} = {self.current_value:<15} "
                f"range: {self.min_value}–{self.max_value}"
            )
        else:
            return f"[switch]  {self.name:<30} = {self.friendly_value}"

    @property
    def friendly_value(self) -> str:
        return FRIENDLY_NAMES.get(self.current_value, self.current_value)


def parse_capabilities(
    capabilities_xml: ET.Element,
    current_values_xml: ET.Element | None = None,
) -> list[EntityDescriptor]:
    """Parse capabilities XML into a list of entity descriptors.

    If current_values_xml is provided, current values are populated from it.
    Otherwise, falls back to the default values embedded in the capabilities XML.
    """
    entities: list[EntityDescriptor] = []
    _walk(capabilities_xml, "", entities)

    if current_values_xml is not None:
        current_map = _build_value_map(current_values_xml)
        for entity in entities:
            if entity.path in current_map:
                entity.current_value = current_map[entity.path]

    _merge_enabled_mode_patterns(entities, current_map if current_values_xml is not None else {})

    return entities


def _walk(
    element: ET.Element,
    parent_path: str,
    entities: list[EntityDescriptor],
) -> None:
    """Recursively walk the capabilities XML tree, extracting entity descriptors."""
    for child in element:
        tag = _strip_ns(child.tag)
        path = f"{parent_path}/{tag}" if parent_path else tag

        if path in SKIP_PATHS:
            continue

        opt = child.attrib.get("opt")
        min_val = child.attrib.get("min")
        max_val = child.attrib.get("max")

        if opt is not None:
            options = [o.strip() for o in opt.split(",")]
            default_value = (child.text or "").strip()

            if _is_switch(options):
                entities.append(EntityDescriptor(
                    path=path,
                    name=ENTITY_NAMES.get(path, _path_to_name(path)),
                    entity_type=EntityType.SWITCH,
                    current_value=default_value,
                ))
            elif len(options) > 1:
                friendly = [FRIENDLY_NAMES.get(o, o) for o in options]
                entities.append(EntityDescriptor(
                    path=path,
                    name=ENTITY_NAMES.get(path, _path_to_name(path)),
                    entity_type=EntityType.SELECT,
                    options=options,
                    friendly_options=friendly,
                    current_value=default_value,
                ))
            # Single-option selects (e.g., ExposureType="manual" on ColorVu) — still
            # expose them so the discovery output is complete and users can see them.
            # The integration can decide later whether to hide single-option entities.
            else:
                entities.append(EntityDescriptor(
                    path=path,
                    name=ENTITY_NAMES.get(path, _path_to_name(path)),
                    entity_type=EntityType.SELECT,
                    options=options,
                    friendly_options=[FRIENDLY_NAMES.get(options[0], options[0])],
                    current_value=default_value,
                ))
        elif min_val is not None and max_val is not None:
            default_value = (child.text or "").strip()
            entities.append(EntityDescriptor(
                path=path,
                name=ENTITY_NAMES.get(path, _path_to_name(path)),
                entity_type=EntityType.NUMBER,
                min_value=float(min_val),
                max_value=float(max_val),
                current_value=default_value,
            ))

        # Recurse into children regardless — there may be nested entities
        if len(child):
            _walk(child, path, entities)


# Values in mode selects that mean "off" — used to detect merged enabled+mode patterns
MODE_OFF_VALUES = {"CLOSE", "close"}


def _merge_enabled_mode_patterns(
    entities: list[EntityDescriptor],
    current_map: dict[str, str],
) -> None:
    """Detect and merge enabled+mode patterns like BLC.

    When a parent element has both an `enabled` switch and a mode select
    with an "off" option (like CLOSE), the switch is redundant — the camera
    UI presents them as a single dropdown. We remove the switch and mark
    the select as the combined control.
    """
    # Index switches and selects by their parent path
    switches_by_parent: dict[str, EntityDescriptor] = {}
    selects_by_parent: dict[str, tuple[EntityDescriptor, str]] = {}

    for e in entities:
        parts = e.path.rsplit("/", 1)
        if len(parts) != 2:
            continue
        parent, leaf = parts
        if e.entity_type == EntityType.SWITCH and leaf == "enabled":
            switches_by_parent[parent] = e
        elif e.entity_type == EntityType.SELECT:
            off_vals = [o for o in e.options if o in MODE_OFF_VALUES]
            if off_vals:
                selects_by_parent[parent] = (e, off_vals[0])

    # Merge matching pairs
    to_remove = []
    for parent, switch in switches_by_parent.items():
        if parent not in selects_by_parent:
            continue
        select, off_val = selects_by_parent[parent]
        select.linked_enabled_path = switch.path
        select.off_value = off_val

        # When the feature is disabled, the mode tag is absent from current
        # values XML. Set the select's current value to the off value.
        enabled_val = current_map.get(switch.path, "")
        if enabled_val.lower() != "true":
            select.current_value = off_val

        to_remove.append(switch)

    for e in to_remove:
        entities.remove(e)


def _build_value_map(root: ET.Element, parent_path: str = "") -> dict[str, str]:
    """Flatten current-values XML into a {path: value} dict."""
    values: dict[str, str] = {}
    for child in root:
        tag = _strip_ns(child.tag)
        path = f"{parent_path}/{tag}" if parent_path else tag
        if child.text and child.text.strip() and not len(child):
            values[path] = child.text.strip()
        if len(child):
            values.update(_build_value_map(child, path))
    return values


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from a tag: {http://...}Tag → Tag."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _is_switch(options: list[str]) -> bool:
    """Check if options represent a boolean switch."""
    normalized = {o.lower() for o in options}
    return normalized == {"true", "false"}


def _path_to_name(path: str) -> str:
    """Generate a fallback human-readable name from an ISAPI path.

    E.g., "NoiseReduce/GeneralMode/generalLevel" → "General Level"
    """
    last = path.rsplit("/", 1)[-1]
    # Insert spaces before uppercase letters: "generalLevel" → "general Level"
    name = ""
    for i, ch in enumerate(last):
        if ch.isupper() and i > 0 and last[i - 1].islower():
            name += " "
        name += ch
    return name.replace("_", " ").title()
