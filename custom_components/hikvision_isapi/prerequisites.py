"""Prerequisite / mutual exclusivity engine for Hikvision ISAPI.

Some camera settings conflict with each other. The camera rejects changes with
machine-readable error codes when conflicts exist. This module handles:

1. Known conflict table — tested relationships between settings
2. Try-fail-retry — if a PUT fails with a conflict error code, auto-resolve
   the conflict and retry

Tested conflicts (from DS-2CD2187G2-LSU and PCI-D18Z2HS):
  - WDR conflicts with HLC and BLC (bidirectional)
  - HLC and BLC can coexist
  - Error codes: WDRNotDisable, MutexWithWDR, HLCNotDisable, BLCNotDisable

IMPORTANT: The camera validates conflicts against its CURRENT state, not the
PUT body. So disabling a blocker and enabling the target must be done in two
sequential PUTs — a single combined PUT is rejected.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .isapi_client import ISAPIClient, PutResult

_LOGGER = logging.getLogger(__name__)

# Known conflict error codes → what to disable first
# Key: subStatusCode from camera, Value: {path: value} to set BEFORE retrying
CONFLICT_RESOLUTIONS: Dict[str, Dict[str, str]] = {
    "WDRNotDisable": {"WDR/mode": "close"},
    "MutexWithWDR": {"WDR/mode": "close"},
    "HLCNotDisable": {"HLC/enabled": "false"},
    "BLCNotDisable": {"BLC/enabled": "false"},
}

# MutexWithWDR is ambiguous — returned both when enabling something while WDR
# is on AND when enabling WDR while something else is on.  When the path being
# set IS WDR, the actual blockers are BLC/HLC, not WDR itself.
_WDR_REVERSE_RESOLUTION: Dict[str, str] = {
    "BLC/enabled": "false",
    "HLC/enabled": "false",
}

MAX_RETRIES = 2


def _get_resolution(sub_status: str, path: str) -> Optional[Dict[str, str]]:
    """Get the right conflict resolution for a given error and target path."""
    resolution = CONFLICT_RESOLUTIONS.get(sub_status)
    if resolution is None:
        return None
    # If the resolution would target the same path we're trying to set,
    # the error is in the reverse direction — disable the other side
    if path in resolution and sub_status == "MutexWithWDR":
        return _WDR_REVERSE_RESOLUTION
    return resolution


async def put_with_prerequisites(
    client: "ISAPIClient",
    path: str,
    value: str,
) -> "PutResult":
    """Set a value, auto-resolving conflicts if needed.

    1. Try the PUT directly
    2. If it fails with a known conflict code, disable the blocker in a
       separate PUT first, then retry the original change
    """
    # First attempt: just set the value
    result = await client.put_setting(path, value)

    if result.success:
        return result

    # Check if the failure is a known conflict we can auto-resolve
    for attempt in range(MAX_RETRIES):
        resolution = _get_resolution(result.sub_status, path)
        if resolution is None:
            _LOGGER.warning(
                "PUT %s=%s failed with unresolvable error: %s",
                path,
                value,
                result.sub_status,
            )
            return result

        _LOGGER.info(
            "Conflict detected (%s) — disabling %s then setting %s=%s",
            result.sub_status,
            resolution,
            path,
            value,
        )

        # Step 1: Disable the blocker in its own PUT
        prereq_result = await client.put_settings(resolution)
        if not prereq_result.success:
            _LOGGER.warning(
                "Failed to disable prerequisite %s: %s",
                resolution,
                prereq_result.sub_status,
            )
            return prereq_result

        # Step 2: Retry the original change
        result = await client.put_setting(path, value)

        if result.success:
            return result

    return result
