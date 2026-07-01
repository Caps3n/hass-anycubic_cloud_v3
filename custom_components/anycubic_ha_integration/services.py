"""Service calls related dependencies for Anycubic Cloud component."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_EVENT_DATA,
    CONF_FILENAME,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)

from .anycubic_cloud_api.data_models.print_response import AnycubicPrintResponse
from .anycubic_cloud_api.data_models.printer import AnycubicPrinter
from .anycubic_cloud_api.data_models.printer_properties import AnycubicMaterialColor
from .const import (
    AC_EVENT_PRINT_CLOUD_START,
    ATTR_ANYCUBIC_EVENT,
    ATTR_CONFIG_ENTRY,
    CONF_BOX_ID,
    CONF_DRY_RUN,
    CONF_FILE_ID,
    CONF_FILEPATH,
    CONF_FINISHED,
    CONF_LAYERS,
    CONF_PRINTER_ID,
    CONF_PRINTER_LAN_IP,
    CONF_PRINTER_NAME,
    CONF_SLOT_COLOR_BLUE,
    CONF_SLOT_COLOR_GREEN,
    CONF_SLOT_COLOR_RED,
    CONF_SLOT_NUMBER,
    CONF_SPEED,
    CONF_SPEED_MODE,
    CONF_TEMPERATURE,
    CONF_TIME,
    CONF_UPLOADED_GCODE_FILE,
    COORDINATOR,
    DOMAIN,
    LOGGER,
    MAX_FILE_UPLOAD_RETRIES,
)
from .helpers import slug_for_printer_entity

if TYPE_CHECKING:
    from .coordinator import AnycubicCloudDataUpdateCoordinator


def build_anycubic_service_schema(
    input_service_schema: dict[Any, Any] = {},
    with_slot_number: bool = False,
    with_slot_colours: bool = False,
    with_opt_box: bool = False,
    with_speed: bool = False,
    with_speed_mode: bool = False,
    with_temperature: bool = False,
    with_time: bool = False,
    with_layers: bool = False,
) -> vol.Schema:
    service_schema = {
        **input_service_schema,
    }

    if with_slot_number:
        service_schema[vol.Required(CONF_SLOT_NUMBER)] = cv.positive_int

    if with_slot_colours:
        service_schema[vol.Required(CONF_SLOT_COLOR_RED)] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        )
        service_schema[vol.Required(CONF_SLOT_COLOR_GREEN)] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        )
        service_schema[vol.Required(CONF_SLOT_COLOR_BLUE)] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        )

    if with_opt_box:
        service_schema[vol.Optional(CONF_BOX_ID)] = cv.positive_int

    if with_speed:
        service_schema[vol.Required(CONF_SPEED)] = cv.positive_int

    if with_speed_mode:
        service_schema[vol.Required(CONF_SPEED_MODE)] = cv.positive_int

    if with_temperature:
        service_schema[vol.Required(CONF_TEMPERATURE)] = cv.positive_int

    if with_time:
        service_schema[vol.Required(CONF_TIME)] = cv.positive_float

    if with_layers:
        service_schema[vol.Required(CONF_LAYERS)] = cv.positive_int

    return vol.Schema(
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
                        {
                            "integration": DOMAIN,
                        }
                    ),
                    vol.Optional(ATTR_DEVICE_ID): cv.string,
                    vol.Optional(CONF_PRINTER_ID): cv.positive_int,
                    **service_schema,
                }
            ),
            cv.has_at_least_one_key(
                ATTR_DEVICE_ID,
                CONF_PRINTER_ID,
            ),
        ),
    )


class AnycubicCloudServiceCall:
    """Parent class for all Anycubic Cloud service calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize service call."""
        self.hass = hass
        self._device_id: str | None = None

    def _get_coordinator(self, service: ServiceCall) -> AnycubicCloudDataUpdateCoordinator:
        """Get AnycubicCloudDataUpdateCoordinator object."""
        entry_id = service.data[ATTR_CONFIG_ENTRY]

        entry = self.hass.config_entries.async_get_entry(entry_id)

        if not entry:
            raise ServiceValidationError(
                "Could not find Anycubic Cloud config entry."
            )

        coordinator: AnycubicCloudDataUpdateCoordinator = self.hass.data[DOMAIN][entry.entry_id][
            COORDINATOR
        ]

        return coordinator

    def _get_printer(self, service: ServiceCall) -> AnycubicPrinter:
        """Get AnycubicPrinter object."""

        coordinator = self._get_coordinator(service)

        if service.data.get(ATTR_DEVICE_ID) is not None:
            device_id = service.data[ATTR_DEVICE_ID]
            if isinstance(device_id, list):
                if len(device_id) == 1:
                    device_id = device_id[0]
                else:
                    raise ServiceValidationError(
                        "Can only call services for one printer at a time."
                    )

            self._device_id = device_id

            printer = coordinator.get_printer_for_device_id(self._device_id)
        else:
            printer_id = service.data[CONF_PRINTER_ID]
            printer = coordinator.get_printer_for_id(printer_id)

        if printer is None:
            raise ServiceValidationError(
                "Could not find Anycubic printer for service call."
            )

        return printer

    def _get_box_id(self, service: ServiceCall) -> int:
        box_id = service.data.get(CONF_BOX_ID)
        if box_id is None:
            box_id = 0

        return box_id

    def _get_slot_num_list(self, service: ServiceCall) -> list[int] | None:
        slot_idx_list = None
        slot_num_list = service.data.get(CONF_SLOT_NUMBER)

        if slot_num_list is not None:
            slot_idx_list = list([x - 1 for x in slot_num_list])

        return slot_idx_list

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        raise NotImplementedError


class BaseMultiColorBoxSetSlot(AnycubicCloudServiceCall):
    """Base for setting multi color box slots."""

    schema = build_anycubic_service_schema(
        with_opt_box=True,
        with_slot_number=True,
        with_slot_colours=True,
    )

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:
        raise NotImplementedError

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        coordinator = self._get_coordinator(service)
        printer = self._get_printer(service)
        box_id = self._get_box_id(service)
        slot_index = service.data[CONF_SLOT_NUMBER] - 1
        slot_color = AnycubicMaterialColor(
            int(service.data[CONF_SLOT_COLOR_RED]),
            int(service.data[CONF_SLOT_COLOR_GREEN]),
            int(service.data[CONF_SLOT_COLOR_BLUE]),
        )
        await self.async_set_box_slot(
            printer=printer,
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )
        await coordinator.force_state_update()


class MultiColorBoxSetSlotPla(BaseMultiColorBoxSetSlot):
    """Set multi color box pla slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_pla_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotPetg(BaseMultiColorBoxSetSlot):
    """Set multi color box petg slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_petg_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotAbs(BaseMultiColorBoxSetSlot):
    """Set multi color box abs slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_abs_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotPacf(BaseMultiColorBoxSetSlot):
    """Set multi color box pacf slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_pacf_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotPc(BaseMultiColorBoxSetSlot):
    """Set multi color box pc slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_pc_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotAsa(BaseMultiColorBoxSetSlot):
    """Set multi color box asa slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_asa_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotHips(BaseMultiColorBoxSetSlot):
    """Set multi color box hips slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_hips_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotPa(BaseMultiColorBoxSetSlot):
    """Set multi color box pa slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_pa_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxSetSlotPlaSe(BaseMultiColorBoxSetSlot):
    """Set multi color box pla se slot."""

    async def async_set_box_slot(
        self,
        printer: AnycubicPrinter,
        slot_index: int,
        slot_color: AnycubicMaterialColor,
        box_id: int,
    ) -> None:

        await printer.multi_color_box_set_pla_se_slot(
            slot_index=slot_index,
            slot_color=slot_color,
            box_id=box_id,
        )


class MultiColorBoxFilamentExtrude(AnycubicCloudServiceCall):
    """Extrude filament."""

    schema = build_anycubic_service_schema(
        input_service_schema={
            vol.Optional(CONF_FINISHED): cv.boolean,
        },
        with_opt_box=True,
        with_slot_number=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer(service)
        box_id = self._get_box_id(service)
        finished = service.data.get(CONF_FINISHED)
        slot_index = service.data[CONF_SLOT_NUMBER] - 1
        await printer.multi_color_box_feed_filament(
            slot_index=slot_index,
            box_id=box_id,
            finish=bool(finished)
        )


class MultiColorBoxFilamentRetract(AnycubicCloudServiceCall):
    """Retract filament."""

    schema = build_anycubic_service_schema(
        with_opt_box=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer(service)
        box_id = self._get_box_id(service)
        await printer.multi_color_box_retract_filament(
            box_id=box_id,
        )


class BasePrintWithFile(AnycubicCloudServiceCall):
    """ Base for print with file service calls """

    schema = build_anycubic_service_schema(
        input_service_schema={
            vol.Required(CONF_UPLOADED_GCODE_FILE): selector.FileSelector(
                selector.FileSelectorConfig(accept=".gcode")
            ),
            vol.Optional(CONF_SLOT_NUMBER): vol.All(cv.ensure_list, [cv.positive_int]),
        }
    )

    def _read_uploaded_file_bytes(
        self, uploaded_file_id: str
    ) -> tuple[str, bytes]:
        with process_uploaded_file(self.hass, uploaded_file_id) as file_path:
            filename = file_path.name
            contents = file_path.read_bytes()

        return filename, contents

    async def _get_gcode_data(
        self,
        service: ServiceCall,
    ) -> tuple[str, bytes]:
        try:
            for x in range(MAX_FILE_UPLOAD_RETRIES):
                try:
                    file_name, gcode_bytes = await self.hass.async_add_executor_job(
                        self._read_uploaded_file_bytes, service.data[CONF_UPLOADED_GCODE_FILE]
                    )
                    break
                except ValueError:
                    if x < MAX_FILE_UPLOAD_RETRIES - 1:
                        await asyncio.sleep(1)
                    else:
                        raise

        except Exception as e:
            LOGGER.warning(f"Gcode file read error: {e}")
            raise ServiceValidationError(
                "Could not read gcode file."
            )

        return file_name, gcode_bytes

    def _async_fire_event(
        self,
        service: ServiceCall,
        printer: AnycubicPrinter,
        print_response: AnycubicPrintResponse,
    ) -> None:
        # Fire event
        data = {
            CONF_PRINTER_ID: printer.id,
            CONF_PRINTER_NAME: printer.name,
            CONF_DEVICE_ID: self._device_id,
            CONF_TYPE: AC_EVENT_PRINT_CLOUD_START,
            CONF_EVENT_DATA: print_response.event_dict,
        }
        self.hass.bus.async_fire(ATTR_ANYCUBIC_EVENT, data)


class PrintAndUploadSaveInCloud(BasePrintWithFile):
    """Print and upload (save in user cloud)."""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        file_name, gcode_bytes = await self._get_gcode_data(service)
        printer = self._get_printer(service)
        slot_idx_list = self._get_slot_num_list(service)

        print_response = await printer.print_and_upload_save_in_cloud(
            file_name=file_name,
            file_bytes=gcode_bytes,
            slot_index_list=slot_idx_list,
        )

        if print_response:
            self._async_fire_event(
                service=service,
                printer=printer,
                print_response=print_response,
            )


class PrintAndUploadNoCloudSave(BasePrintWithFile):
    """Print and upload (no user cloud save)."""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        file_name, gcode_bytes = await self._get_gcode_data(service)
        printer = self._get_printer(service)
        slot_idx_list = self._get_slot_num_list(service)

        print_response = await printer.print_and_upload_no_cloud_save(
            file_name=file_name,
            file_bytes=gcode_bytes,
            slot_index_list=slot_idx_list,
        )

        if print_response:
            self._async_fire_event(
                service=service,
                printer=printer,
                print_response=print_response,
            )


class BasePrintExistingFile(AnycubicCloudServiceCall):
    """Base for printing a file that already exists on the printer/USB storage."""

    schema = build_anycubic_service_schema(
        input_service_schema={
            vol.Required(CONF_FILENAME): cv.string,
            vol.Optional(CONF_FILEPATH, default=""): cv.string,
            vol.Optional(CONF_SLOT_NUMBER): vol.All(cv.ensure_list, [cv.positive_int]),
        }
    )


class PrintFileLocal(BasePrintExistingFile):
    """Print a file already stored on the printer's local storage."""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer(service)
        file_name = service.data[CONF_FILENAME]
        file_path = service.data.get(CONF_FILEPATH, "")
        slot_idx_list = self._get_slot_num_list(service)

        if slot_idx_list is not None:
            LOGGER.warning(
                "print_file_local: ACE slot mapping for printer-local files is built "
                "from the spools currently loaded in the requested slots, not from the "
                "file itself (unlike cloud prints, slot count/order can't be validated "
                "against the gcode). Make sure slot order matches what the file expects."
            )

        await printer.print_local_file(
            file_name=file_name,
            file_path=file_path,
            slot_index_list=slot_idx_list,
        )


class PrintFileUdisk(BasePrintExistingFile):
    """Print a file already stored on a USB disk plugged into the printer."""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer(service)
        file_name = service.data[CONF_FILENAME]
        file_path = service.data.get(CONF_FILEPATH, "")
        slot_idx_list = self._get_slot_num_list(service)

        if slot_idx_list is not None:
            LOGGER.warning(
                "print_file_udisk: ACE slot mapping for USB files is built from the "
                "spools currently loaded in the requested slots, not from the file "
                "itself (unlike cloud prints, slot count/order can't be validated "
                "against the gcode). Make sure slot order matches what the file expects."
            )

        await printer.print_udisk_file(
            file_name=file_name,
            file_path=file_path,
            slot_index_list=slot_idx_list,
        )


class BaseDeletePrinterFile(AnycubicCloudServiceCall):
    """ Base for printer file deletions """

    schema = build_anycubic_service_schema(
        input_service_schema={
            vol.Required(CONF_FILENAME): cv.string,
        }
    )


class DeleteFileLocal(BaseDeletePrinterFile):
    """Delete a file (local)"""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        file_name = service.data[CONF_FILENAME]
        printer = self._get_printer(service)

        try:

            await printer.delete_local_file(
                file_name=file_name,
            )
            await asyncio.sleep(2)
            await printer.request_local_file_list()
            await asyncio.sleep(5)
            await printer.request_local_file_list()

        except Exception as error:
            raise HomeAssistantError(error) from error


class DeleteFileUdisk(BaseDeletePrinterFile):
    """Delete a file (USB Disk)"""

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        file_name = service.data[CONF_FILENAME]
        printer = self._get_printer(service)

        try:

            await printer.delete_udisk_file(
                file_name=file_name,
            )
            await asyncio.sleep(2)
            await printer.request_udisk_file_list()
            await asyncio.sleep(5)
            await printer.request_udisk_file_list()

        except Exception as error:
            raise HomeAssistantError(error) from error


class DeleteFileCloud(AnycubicCloudServiceCall):
    """Delete a file (Cloud)"""

    schema = build_anycubic_service_schema(
        input_service_schema={
            vol.Required(CONF_FILE_ID): cv.positive_int,
        }
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        file_id = service.data[CONF_FILE_ID]

        coordinator = self._get_coordinator(service)

        try:

            success = await coordinator.anycubic_api.delete_file_from_cloud(
                file_id=file_id,
            )

        except Exception as error:
            raise HomeAssistantError(error) from error

        if not success:
            raise HomeAssistantError("Failed to delete cloud file.")

        else:
            await asyncio.sleep(5)
            await coordinator.refresh_cloud_files()


class BaseChangePrintSetting(AnycubicCloudServiceCall):
    """ Base for change print setting service calls """

    def _get_printer_if_printing(
        self,
        service: ServiceCall,
    ) -> AnycubicPrinter:
        printer = self._get_printer(service)

        if not printer.is_busy:
            raise ServiceValidationError(
                "Printer is currently idle."
            )

        if not printer.latest_project:
            raise ServiceValidationError(
                "No print project found."
            )

        if not printer.latest_project_print_in_progress:
            raise ServiceValidationError(
                "Printer is not currently printing."
            )

        return printer


class ChangePrintSpeedMode(BaseChangePrintSetting):
    """Change print speed mode"""

    schema = build_anycubic_service_schema(
        with_speed_mode=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_speed_mode(
                service.data[CONF_SPEED_MODE],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintTargetNozzleTemperature(BaseChangePrintSetting):
    """Change print target nozzle temperature"""

    schema = build_anycubic_service_schema(
        with_temperature=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_target_nozzle_temp(
                service.data[CONF_TEMPERATURE],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintTargetHotbedTemperature(BaseChangePrintSetting):
    """Change print target hotbed temperature"""

    schema = build_anycubic_service_schema(
        with_temperature=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_target_hotbed_temp(
                service.data[CONF_TEMPERATURE],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintFanSpeed(BaseChangePrintSetting):
    """Change print fan speed"""

    schema = build_anycubic_service_schema(
        with_speed=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_fan_speed_pct(
                service.data[CONF_SPEED],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintAuxFanSpeed(BaseChangePrintSetting):
    """Change print aux fan speed"""

    schema = build_anycubic_service_schema(
        with_speed=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_aux_fan_speed_pct(
                service.data[CONF_SPEED],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintBoxFanSpeed(BaseChangePrintSetting):
    """Change print box fan speed"""

    schema = build_anycubic_service_schema(
        with_speed=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_box_fan_level(
                service.data[CONF_SPEED],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintBottomLayers(BaseChangePrintSetting):
    """Change print bottom layers"""

    schema = build_anycubic_service_schema(
        with_layers=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_bottom_layers(
                service.data[CONF_LAYERS],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintBottomTime(BaseChangePrintSetting):
    """Change print bottom time"""

    schema = build_anycubic_service_schema(
        with_time=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_bottom_time(
                service.data[CONF_TIME],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintOffTime(BaseChangePrintSetting):
    """Change print off time"""

    schema = build_anycubic_service_schema(
        with_time=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_off_time(
                service.data[CONF_TIME],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class ChangePrintOnTime(BaseChangePrintSetting):
    """Change print on time"""

    schema = build_anycubic_service_schema(
        with_time=True,
    )

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""

        printer = self._get_printer_if_printing(service)

        try:
            await printer.change_print_setting_on_time(
                service.data[CONF_TIME],
            )
        except Exception as error:
            raise HomeAssistantError(error) from error


class SetPrinterLanIp(AnycubicCloudServiceCall):
    """Set or clear the local LAN IP address for a printer (e.g. Kobra X camera)."""

    schema = vol.Schema({
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Optional(CONF_PRINTER_LAN_IP, default=""): cv.string,
    })

    async def async_call_service(self, service: ServiceCall) -> None:
        """Update the printer_lan_ip option and reload the config entry."""
        coordinator = self._get_coordinator(service)
        lan_ip = str(service.data.get(CONF_PRINTER_LAN_IP, "")).strip()

        new_options = dict(coordinator.entry.options)
        new_options[CONF_PRINTER_LAN_IP] = lan_ip

        self.hass.config_entries.async_update_entry(
            coordinator.entry,
            options=new_options,
        )
        LOGGER.debug("set_printer_lan_ip: updated LAN IP to '%s'", lan_ip)


class MigrateEntityIds(AnycubicCloudServiceCall):
    """Rename existing entity_ids to the stable, language-independent slug.

    New entities already get a stable English object_id (see
    AnycubicCloudEntity), but that only applies at first registration.
    Entities registered before that (or while HA ran in a non-English
    language) can still carry a localized entity_id. This lets a user
    opt in to renaming those, without touching entities that already
    match or that belong to another integration.
    """

    schema = vol.Schema({
        vol.Required(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector(
            {"integration": DOMAIN}
        ),
        vol.Optional(CONF_DRY_RUN, default=True): cv.boolean,
    })

    async def async_call_service(self, service: ServiceCall) -> None:
        """Execute service call."""
        coordinator = self._get_coordinator(service)
        dry_run = bool(service.data.get(CONF_DRY_RUN, True))

        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)

        entries = er.async_entries_for_config_entry(
            entity_registry, coordinator.entry.entry_id
        )

        renamed = 0
        skipped = 0

        for entry in entries:
            if entry.platform != DOMAIN or "-" not in entry.unique_id:
                continue

            if entry.device_id is None:
                continue

            device = device_registry.async_get(entry.device_id)
            device_name = device.name_by_user or device.name if device else None

            if not device_name:
                continue

            entity_key = entry.unique_id.split("-", 1)[1]
            desired_entity_id = f"{entry.domain}.{slug_for_printer_entity(device_name, entity_key)}"

            if desired_entity_id == entry.entity_id:
                continue

            existing = entity_registry.async_get(desired_entity_id)
            if existing is not None and existing.unique_id != entry.unique_id:
                LOGGER.warning(
                    "migrate_entity_ids: skipping %s -> %s, target entity_id is already "
                    "in use by a different entity.",
                    entry.entity_id,
                    desired_entity_id,
                )
                skipped += 1
                continue

            if dry_run:
                LOGGER.warning(
                    "migrate_entity_ids (dry_run): would rename %s -> %s",
                    entry.entity_id,
                    desired_entity_id,
                )
            else:
                entity_registry.async_update_entity(
                    entry.entity_id, new_entity_id=desired_entity_id
                )
                LOGGER.warning(
                    "migrate_entity_ids: renamed %s -> %s",
                    entry.entity_id,
                    desired_entity_id,
                )

            renamed += 1

        LOGGER.warning(
            "migrate_entity_ids: %s %d entit%s (dry_run=%s), %d skipped due to collisions.",
            "would rename" if dry_run else "renamed",
            renamed,
            "y" if renamed == 1 else "ies",
            dry_run,
            skipped,
        )


SERVICES = (
    ("multi_color_box_set_slot_pla", MultiColorBoxSetSlotPla),
    ("multi_color_box_set_slot_petg", MultiColorBoxSetSlotPetg),
    ("multi_color_box_set_slot_abs", MultiColorBoxSetSlotAbs),
    ("multi_color_box_set_slot_pacf", MultiColorBoxSetSlotPacf),
    ("multi_color_box_set_slot_pc", MultiColorBoxSetSlotPc),
    ("multi_color_box_set_slot_asa", MultiColorBoxSetSlotAsa),
    ("multi_color_box_set_slot_hips", MultiColorBoxSetSlotHips),
    ("multi_color_box_set_slot_pa", MultiColorBoxSetSlotPa),
    ("multi_color_box_set_slot_pla_se", MultiColorBoxSetSlotPlaSe),
    ("multi_color_box_filament_extrude", MultiColorBoxFilamentExtrude),
    ("multi_color_box_filament_retract", MultiColorBoxFilamentRetract),
    ("print_and_upload_save_in_cloud", PrintAndUploadSaveInCloud),
    ("print_and_upload_no_cloud_save", PrintAndUploadNoCloudSave),
    ("print_file_local", PrintFileLocal),
    ("print_file_udisk", PrintFileUdisk),
    ("delete_file_local", DeleteFileLocal),
    ("delete_file_udisk", DeleteFileUdisk),
    ("delete_file_cloud", DeleteFileCloud),
    ("change_print_speed_mode", ChangePrintSpeedMode),
    ("change_print_target_nozzle_temperature", ChangePrintTargetNozzleTemperature),
    ("change_print_target_hotbed_temperature", ChangePrintTargetHotbedTemperature),
    ("change_print_fan_speed", ChangePrintFanSpeed),
    ("change_print_aux_fan_speed", ChangePrintAuxFanSpeed),
    ("change_print_box_fan_speed", ChangePrintBoxFanSpeed),
    ("change_print_bottom_layers", ChangePrintBottomLayers),
    ("change_print_bottom_time", ChangePrintBottomTime),
    ("change_print_off_time", ChangePrintOffTime),
    ("change_print_on_time", ChangePrintOnTime),
    ("set_printer_lan_ip", SetPrinterLanIp),
    ("migrate_entity_ids", MigrateEntityIds),
)
