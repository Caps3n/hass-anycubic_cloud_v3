"""Select entities for Anycubic Cloud Printers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DOMAIN,
    PrinterEntityType,
)
from .entity import AnycubicCloudEntity, AnycubicCloudEntityDescription
from .helpers import printer_attributes_for_key, printer_state_for_key

if TYPE_CHECKING:
    from .coordinator import AnycubicCloudDataUpdateCoordinator

# Fallback-Modi wenn der Drucker keine available_modes liefert (FDM-Drucker)
_DEFAULT_SPEED_MODES: list[dict[str, Any]] = [
    {"description": "Silent", "mode": 0},
    {"description": "Normal", "mode": 1},
    {"description": "Ludicrous", "mode": 2},
]


@dataclass(frozen=True)
class AnycubicSelectEntityDescription(
    SelectEntityDescription, AnycubicCloudEntityDescription
):
    """Describes an Anycubic Cloud select entity."""


SELECT_TYPES: list[AnycubicCloudEntityDescription] = [
    AnycubicSelectEntityDescription(
        key="job_speed_mode",
        translation_key="job_speed_mode",
        printer_entity_type=PrinterEntityType.FDM,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anycubic Cloud select entities."""
    coordinator: AnycubicCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    coordinator.add_entities_for_seen_printers(
        async_add_entities=async_add_entities,
        entity_constructor=AnycubicCloudSelect,
        platform=Platform.SELECT,
        available_descriptors=SELECT_TYPES,
    )


class AnycubicCloudSelect(AnycubicCloudEntity, SelectEntity):
    """Speed-Mode select entity for an Anycubic FDM printer."""

    entity_description: AnycubicSelectEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AnycubicCloudDataUpdateCoordinator,
        printer_id: int,
        entity_description: AnycubicSelectEntityDescription,
    ) -> None:
        super().__init__(hass, coordinator, printer_id, entity_description)
        self._attr_options = self._build_options()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _available_modes(self) -> list[dict[str, Any]]:
        """Return the list of speed-mode dicts from coordinator attributes."""
        attr = printer_attributes_for_key(
            self.coordinator, self._printer_id, self.entity_description.key
        )
        if attr and attr.get("available_modes"):
            modes: list[dict[str, Any]] = attr["available_modes"]
            return modes
        return _DEFAULT_SPEED_MODES

    def _build_options(self) -> list[str]:
        return [str(m["description"]) for m in self._available_modes()]

    def _mode_for_title(self, title: str) -> int | None:
        for m in self._available_modes():
            if m["description"] == title:
                return int(m["mode"])
        return None

    # ------------------------------------------------------------------
    # HA properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Only available while a print job is running."""
        in_progress = printer_state_for_key(
            self.coordinator, self._printer_id, "job_in_progress"
        )
        return bool(in_progress)

    @property
    def current_option(self) -> str | None:
        state = printer_state_for_key(
            self.coordinator, self._printer_id, self.entity_description.key
        )
        return str(state) if state is not None else None

    @property
    def options(self) -> list[str]:
        opts = self._build_options()
        self._attr_options = opts
        return opts

    # ------------------------------------------------------------------
    # HA action
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        """Send speed-mode change to the printer via MQTT."""
        mode_int = self._mode_for_title(option)
        if mode_int is None:
            raise HomeAssistantError(f"Unbekannter Speed-Mode: {option!r}")

        printer = self.coordinator.get_printer_for_id(self._printer_id)
        if printer is None:
            raise HomeAssistantError("Drucker nicht gefunden.")

        try:
            await printer.change_print_setting_speed_mode(mode_int)
        except Exception as err:
            raise HomeAssistantError(err) from err

        await self.coordinator.force_state_update()
