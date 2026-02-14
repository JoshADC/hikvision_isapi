"""Async ISAPI client for Hikvision cameras.

Handles digest authentication, XML fetching, and read-modify-write for
/ISAPI/Image/channels/1 endpoints. Uses httpx for async HTTP with digest auth.

The camera requires the FULL ImageChannel XML on every PUT — partial documents
are rejected with Device Error. So every write is a read-modify-write cycle:
  1. GET current full XML (raw bytes)
  2. Find and replace target values in the raw string (preserving exact XML)
  3. PUT the barely-modified document back

IMPORTANT: We CANNOT use ET.tostring() for PUT bodies — ElementTree normalizes
away the repeated xmlns declarations on child elements that Hikvision cameras
require. Raw string manipulation is the only reliable approach.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

_LOGGER = logging.getLogger(__name__)

ISAPI_NS = "http://www.hikvision.com/ver20/XMLSchema"
NS = {"ns": ISAPI_NS}
TIMEOUT = 10.0


@dataclass
class DeviceInfo:
    """Camera device information from /ISAPI/System/deviceInfo."""

    model: str
    serial_number: str
    firmware_version: str
    firmware_build: str
    mac_address: str
    device_name: str

    @property
    def unique_id(self) -> str:
        """MAC-based unique ID for the device registry."""
        return self.mac_address.replace(":", "").lower()


@dataclass
class PutResult:
    """Result of a PUT to ISAPI."""

    success: bool
    status_code: int
    sub_status: str  # e.g., "WDRNotDisable", "ok", "deviceError"

    @classmethod
    def from_xml(cls, root: ET.Element, http_status: int) -> PutResult:
        """Parse a ResponseStatus XML into a PutResult."""
        status_str = _text(root, "ns:statusString")
        sub_status = _text(root, "ns:subStatusCode", "ok")
        success = status_str == "OK" and http_status == 200
        return cls(
            success=success,
            status_code=http_status,
            sub_status=sub_status,
        )


class ISAPIClient:
    """Async HTTP client for Hikvision ISAPI with digest auth."""

    def __init__(self, host: str, username: str, password: str, channel: int = 1):
        self.host = host
        self.base_url = f"http://{host}"
        self.channel = channel
        self._auth = httpx.DigestAuth(username, password)
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> ET.Element:
        client = await self._ensure_client()
        url = f"{self.base_url}{path}"
        resp = await client.get(url)
        resp.raise_for_status()
        return ET.fromstring(resp.content)

    async def _get_raw(self, path: str) -> bytes:
        """GET and return raw bytes (preserves XML exactly as camera sends it)."""
        client = await self._ensure_client()
        url = f"{self.base_url}{path}"
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

    async def get_device_info(self) -> DeviceInfo:
        """Fetch device info. Also used to validate credentials."""
        root = await self._get("/ISAPI/System/deviceInfo")
        return DeviceInfo(
            model=_text(root, "ns:model"),
            serial_number=_text(root, "ns:serialNumber"),
            firmware_version=_text(root, "ns:firmwareVersion"),
            firmware_build=_text(root, "ns:firmwareReleasedDate"),
            mac_address=_text(root, "ns:macAddress"),
            device_name=_text(root, "ns:deviceName"),
        )

    async def get_capabilities(self) -> ET.Element:
        """Fetch image capabilities XML for the channel."""
        return await self._get(
            f"/ISAPI/Image/channels/{self.channel}/capabilities"
        )

    async def get_current_values(self) -> ET.Element:
        """Fetch current image settings XML for the channel."""
        return await self._get(f"/ISAPI/Image/channels/{self.channel}")

    async def put_setting(
        self, path: str, value: str
    ) -> PutResult:
        """Set a single ISAPI setting via read-modify-write.

        Fetches the full current XML, modifies the element at `path`, and
        PUTs the entire document back.
        """
        return await self.put_settings({path: value})

    async def put_settings(
        self, changes: Dict[str, str]
    ) -> PutResult:
        """Set multiple ISAPI settings in a single PUT.

        Uses raw string manipulation to preserve the exact XML format the
        camera sends (including repeated xmlns declarations on child elements).
        ET.tostring() mangles these, causing the camera to reject with deviceError.
        """
        # Read current full XML
        raw = await self._get_raw(
            f"/ISAPI/Image/channels/{self.channel}"
        )
        xml_str = raw.decode("utf-8")

        # Parse a copy with ET to find current values (read-only)
        tree = ET.fromstring(raw)

        for path, new_value in changes.items():
            element = _find_by_path(tree, path)
            if element is None:
                _LOGGER.warning("Path not found in XML: %s", path)
                continue

            old_value = element.text or ""
            if old_value == new_value:
                _LOGGER.debug("Skipping %s (already %s)", path, new_value)
                continue

            _LOGGER.debug("Setting %s = %s (was %s)", path, new_value, old_value)
            xml_str = _raw_replace(xml_str, path, old_value, new_value)
            # Update ET tree so subsequent changes see updated values
            element.text = new_value

        # PUT the minimally-modified XML back
        client = await self._ensure_client()
        url = f"{self.base_url}/ISAPI/Image/channels/{self.channel}"
        resp = await client.put(
            url,
            content=xml_str.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
        )

        root = ET.fromstring(resp.content)
        result = PutResult.from_xml(root, resp.status_code)

        if not result.success:
            _LOGGER.warning(
                "PUT failed for %s: %s (HTTP %d)",
                changes,
                result.sub_status,
                result.status_code,
            )

        return result

    async def put_setting_with_enable(
        self,
        enabled_path: str,
        mode_path: str,
        mode_value: str,
    ) -> PutResult:
        """Enable a feature and set its mode in one PUT.

        Handles the case where the mode tag doesn't exist in the XML when
        the feature is disabled (e.g., BLCMode disappears when BLC is off).
        """
        raw = await self._get_raw(
            f"/ISAPI/Image/channels/{self.channel}"
        )
        xml_str = raw.decode("utf-8")
        tree = ET.fromstring(raw)

        # Set enabled=true
        enabled_elem = _find_by_path(tree, enabled_path)
        if enabled_elem is not None:
            old_enabled = enabled_elem.text or ""
            if old_enabled != "true":
                _LOGGER.debug(
                    "Setting %s = true (was %s)", enabled_path, old_enabled
                )
                xml_str = _raw_replace(
                    xml_str, enabled_path, old_enabled, "true"
                )

        # Set or insert mode value
        mode_elem = _find_by_path(tree, mode_path)
        if mode_elem is not None:
            old_mode = mode_elem.text or ""
            _LOGGER.debug(
                "Setting %s = %s (was %s)", mode_path, mode_value, old_mode
            )
            xml_str = _raw_replace(
                xml_str, mode_path, old_mode, mode_value
            )
        else:
            _LOGGER.debug(
                "Inserting %s = %s (tag was absent)", mode_path, mode_value
            )
            xml_str = _raw_insert_after(
                xml_str, enabled_path, mode_path, mode_value
            )

        # PUT
        client = await self._ensure_client()
        url = f"{self.base_url}/ISAPI/Image/channels/{self.channel}"
        resp = await client.put(
            url,
            content=xml_str.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
        )

        root = ET.fromstring(resp.content)
        result = PutResult.from_xml(root, resp.status_code)

        if not result.success:
            _LOGGER.warning(
                "PUT failed for enable %s + %s=%s: %s (HTTP %d)",
                enabled_path,
                mode_path,
                mode_value,
                result.sub_status,
                result.status_code,
            )

        return result


def _raw_insert_after(
    xml_str: str, after_path: str, new_path: str, new_value: str
) -> str:
    """Insert a new XML element after an existing one, within parent scope.

    Used when a tag (like BLCMode) doesn't exist in the XML and needs to
    be added after a sibling (like BLC/enabled).
    """
    after_parts = after_path.split("/")
    after_tag = after_parts[-1]
    new_tag = new_path.split("/")[-1]

    if len(after_parts) >= 2:
        parent_tag = after_parts[-2]
        parent_open = re.search(
            rf"<{re.escape(parent_tag)}[\s>]", xml_str
        )
        if parent_open:
            close_tag = f"</{parent_tag}>"
            close_pos = xml_str.find(close_tag, parent_open.start())
            if close_pos != -1:
                # Find the closing tag of the "after" element within parent
                block = xml_str[parent_open.start():close_pos]
                after_close = f"</{after_tag}>"
                after_close_pos = block.find(after_close)
                if after_close_pos != -1:
                    abs_pos = (
                        parent_open.start()
                        + after_close_pos
                        + len(after_close)
                    )
                    new_element = f"\n<{new_tag}>{new_value}</{new_tag}>"
                    return (
                        xml_str[:abs_pos]
                        + new_element
                        + xml_str[abs_pos:]
                    )

    _LOGGER.warning("Could not insert %s after %s", new_path, after_path)
    return xml_str


def _raw_replace(xml_str: str, path: str, old_value: str, new_value: str) -> str:
    """Replace an element's text value in raw XML, using parent context.

    For a path like "BLC/enabled", finds the <BLC> block first, then replaces
    <enabled>old</enabled> within that block. This prevents accidentally
    changing <enabled> in a different section (e.g., HLC/enabled).
    """
    parts = path.split("/")
    leaf_tag = parts[-1]
    leaf_pat = (
        rf"(<{re.escape(leaf_tag)}(?:\s[^>]*)?>)"
        rf"{re.escape(old_value)}"
        rf"(</{re.escape(leaf_tag)}>)"
    )
    replacement = rf"\g<1>{new_value}\g<2>"

    if len(parts) >= 2:
        # Scope the replacement within the immediate parent block
        parent_tag = parts[-2]
        parent_open = re.search(
            rf"<{re.escape(parent_tag)}[\s>]", xml_str
        )
        if parent_open:
            close_tag = f"</{parent_tag}>"
            close_pos = xml_str.find(close_tag, parent_open.start())
            if close_pos != -1:
                block_end = close_pos + len(close_tag)
                block = xml_str[parent_open.start():block_end]
                new_block = re.sub(leaf_pat, replacement, block, count=1)
                if new_block != block:
                    return (
                        xml_str[:parent_open.start()]
                        + new_block
                        + xml_str[block_end:]
                    )

    # Fallback: replace first match globally
    return re.sub(leaf_pat, replacement, xml_str, count=1)


def _find_by_path(root: ET.Element, path: str) -> Optional[ET.Element]:
    """Find an element by slash-separated path, handling namespaces.

    Path like "Exposure/OverexposeSuppress/enabled" finds the element
    regardless of XML namespace prefixes.
    """
    parts = path.split("/")
    current = root
    for part in parts:
        found = None
        for child in current:
            tag = _strip_ns(child.tag)
            if tag == part:
                found = child
                break
        if found is None:
            return None
        current = found
    return current


def _strip_ns(tag: str) -> str:
    """Strip XML namespace: {http://...}Tag → Tag."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _text(element: ET.Element, xpath: str, default: str = "") -> str:
    node = element.find(xpath, NS)
    return node.text.strip() if node is not None and node.text else default
