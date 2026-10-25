"""Match a locally/USB-stored print file to its cloud project preview image."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .anycubic_cloud_api.data_models.project import AnycubicProject

PREVIEW_FILENAME_SUFFIXES = (".gcode.3mf", ".gcode.gz", ".gcode", ".3mf")


def normalize_print_filename(filename: str) -> str:
    """Reduce a print filename to a bare, case-insensitive comparison key."""
    base_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip().casefold()

    for suffix in PREVIEW_FILENAME_SUFFIXES:
        if base_name.endswith(suffix):
            return base_name[:-len(suffix)]

    return base_name


def find_preview_image_url(
    projects: list[AnycubicProject],
    printer_id: int,
    filename: str,
) -> str | None:
    """Return the image URL of the cloud project matching a local/USB filename."""
    target = normalize_print_filename(filename)

    if not target:
        return None

    for project in projects:
        if (
            project.printer_id == printer_id and
            project.image_url and
            normalize_print_filename(project.name) == target
        ):
            return project.image_url

    return None
