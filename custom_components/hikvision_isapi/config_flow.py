"""Config flow for Hikvision ISAPI integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN
from .isapi_client import DeviceInfo, ISAPIClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default="admin"): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_credentials(
    host: str, username: str, password: str
) -> tuple[Optional[DeviceInfo], Dict[str, str]]:
    """Return (device_info, {}) on success or (None, errors) on failure."""
    client = ISAPIClient(host, username, password)
    try:
        device_info = await client.get_device_info()
    except httpx.HTTPStatusError as err:
        if err.response.status_code == 401:
            return None, {"base": "invalid_auth"}
        _LOGGER.error("ISAPI HTTP error: %s", err)
        return None, {"base": "cannot_connect"}
    except (httpx.ConnectError, httpx.TimeoutException):
        return None, {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected error during config flow")
        return None, {"base": "unknown"}
    finally:
        await client.close()
    return device_info, {}


class HikvisionISAPIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hikvision ISAPI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle the initial step: host + credentials."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            device_info, errors = await _validate_credentials(
                host, username, password
            )
            if device_info is not None:
                # Use MAC as unique ID to prevent duplicate entries
                await self.async_set_unique_id(device_info.unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{device_info.model} ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure: let the user change host or credentials."""
        entry = self._get_reconfigure_entry()
        errors: Dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            device_info, errors = await _validate_credentials(
                host, username, password
            )
            if device_info is not None:
                # Ensure the new host still points at the SAME physical camera
                # (MAC match) — prevents accidentally repointing an entry at a
                # different camera, which would leave its entities orphaned.
                await self.async_set_unique_id(device_info.unique_id)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        # Prefill host + username from current entry; leave password blank.
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data[CONF_HOST]
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
