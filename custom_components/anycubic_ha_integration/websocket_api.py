"""WebSocket API for the Anycubic Cloud frontend panel."""
from __future__ import annotations

import base64
import time
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aiohttp import ClientError, ClientTimeout
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COORDINATOR, DOMAIN
from .file_preview import find_preview_image_url, normalize_print_filename

if TYPE_CHECKING:
    from .coordinator import AnycubicCloudDataUpdateCoordinator

WS_TYPE_FILE_PREVIEW = f"{DOMAIN}/file_preview"

PREVIEW_CACHE_KEY = "file_preview_cache"
PREVIEW_CACHE_TTL_SECONDS = 300
PREVIEW_CACHE_MAX_ENTRIES = 24
PREVIEW_MAX_BYTES = 1024 * 1024
PREVIEW_FETCH_TIMEOUT_SECONDS = 15


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the Anycubic Cloud websocket commands, once per HA instance."""
    if hass.data.get(f"{DOMAIN}_websocket_api_registered"):
        return

    websocket_api.async_register_command(hass, websocket_file_preview)
    hass.data[f"{DOMAIN}_websocket_api_registered"] = True


async def _fetch_preview_data_url(hass: HomeAssistant, image_url: str) -> str | None:
    """Fetch a project preview image and return it as a bounded data URL."""
    if not image_url.startswith("https://"):
        return None

    session = async_get_clientsession(hass)

    try:
        async with session.get(
            image_url,
            timeout=ClientTimeout(total=PREVIEW_FETCH_TIMEOUT_SECONDS),
        ) as response:
            if response.status != 200:
                return None

            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/"):
                return None

            if response.content_length is not None and response.content_length > PREVIEW_MAX_BYTES:
                return None

            body = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > PREVIEW_MAX_BYTES:
                    return None

            if not body:
                return None
    except (ClientError, TimeoutError):
        return None

    return f"data:{content_type};base64,{base64.b64encode(bytes(body)).decode('ascii')}"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_FILE_PREVIEW,
        vol.Required("config_entry"): str,
        vol.Required("device_id"): str,
        vol.Required("filename"): str,
    }
)
@websocket_api.async_response
async def websocket_file_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a cached-cloud-project preview image for a local/USB file, if one exists."""
    entry_data = hass.data.get(DOMAIN, {}).get(msg["config_entry"])
    if not entry_data:
        connection.send_error(
            msg["id"], "config_entry_not_found", "Could not find Anycubic Cloud config entry."
        )
        return

    coordinator: AnycubicCloudDataUpdateCoordinator = entry_data[COORDINATOR]
    printer = coordinator.get_printer_for_device_id(msg["device_id"])
    if printer is None:
        connection.send_error(
            msg["id"], "printer_not_found", "Could not find Anycubic printer."
        )
        return

    cache_key = (printer.id, normalize_print_filename(msg["filename"]))
    cache: dict[tuple[int, str], tuple[float, str | None]] = entry_data.setdefault(
        PREVIEW_CACHE_KEY, {}
    )

    now = time.monotonic()
    cached_entry = cache.get(cache_key)
    if cached_entry is not None and now - cached_entry[0] < PREVIEW_CACHE_TTL_SECONDS:
        connection.send_result(msg["id"], {"image": cached_entry[1]})
        return

    try:
        projects = await coordinator.anycubic_api.list_all_projects()
        image_url = find_preview_image_url(projects, printer.id, msg["filename"])
        image_data = await _fetch_preview_data_url(hass, image_url) if image_url else None
    except Exception:  # noqa: BLE001 - never fail the panel over a missing preview
        connection.send_result(msg["id"], {"image": None})
        return

    if len(cache) >= PREVIEW_CACHE_MAX_ENTRIES:
        oldest_key = min(cache, key=lambda key: cache[key][0])
        cache.pop(oldest_key, None)
    cache[cache_key] = (now, image_data)

    connection.send_result(msg["id"], {"image": image_data})
