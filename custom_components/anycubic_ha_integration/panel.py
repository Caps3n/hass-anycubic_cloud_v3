"""Anycubic Cloud frontend panel."""
from __future__ import annotations

import os
from typing import Any

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    CARD_FILENAME,
    CARD_URL,
    CUSTOM_COMPONENTS,
    DOMAIN,
    INTEGRATION_FOLDER,
    LOGGER,
    PANEL_FILENAME,
    PANEL_FOLDER,
    PANEL_ICON,
    PANEL_NAME,
    PANEL_TITLE,
)
from .helpers import extract_panel_card_config

PANEL_URL = "/anycubic-cloud-panel-static"


def process_card_config(
    conf_object: Any,
) -> dict[str, Any]:
    if isinstance(conf_object, dict):
        return extract_panel_card_config(conf_object)
    else:
        return {}


async def async_register_panel(
    hass: HomeAssistant,
    conf_object: Any,
    camera_entity_map: dict[str, str] | None = None,
) -> None:
    """Register the Anycubic Cloud frontend panel and Lovelace card."""
    if DOMAIN not in hass.data.get("frontend_panels", {}):
        root_dir = os.path.join(hass.config.path(CUSTOM_COMPONENTS), INTEGRATION_FOLDER)
        panel_dir = os.path.join(root_dir, PANEL_FOLDER)
        view_url = os.path.join(panel_dir, PANEL_FILENAME)
        card_url = os.path.join(panel_dir, CARD_FILENAME)

        try:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(PANEL_URL, view_url, cache_headers=False),
                    StaticPathConfig(CARD_URL, card_url, cache_headers=False),
                ]
            )
        except RuntimeError as e:
            if "already registered" not in str(e):
                raise e

        # Auto-register the card as a Lovelace extra module so users don't need
        # to install the separate hass-anycubic_card HACS plugin.
        # DATA_EXTRA_MODULE_URL = "frontend_extra_module_url" (stable HA internal key)
        hass.data.setdefault("frontend_extra_module_url", set()).add(CARD_URL)
        LOGGER.debug("Registered Anycubic card as Lovelace extra module: %s", CARD_URL)

        conf = process_card_config(conf_object)

        if camera_entity_map:
            conf["cameraEntityIds"] = dict(camera_entity_map)

        LOGGER.debug(f"Processed panel config: {conf}")

        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_NAME,
            frontend_url_path=DOMAIN,
            module_url=PANEL_URL,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
            config=conf,
        )


def async_unregister_panel(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, DOMAIN)
    LOGGER.debug("Removing panel")
