"""Support for Anycubic Cloud camera."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DOMAIN,
    LOGGER,
    PrinterEntityType,
)
from .entity import AnycubicCloudEntity, AnycubicCloudEntityDescription

if TYPE_CHECKING:
    from .coordinator import AnycubicCloudDataUpdateCoordinator

# Tencent Cloud IoT Video constants
_TC_HOST = "iottav.tencentcloudapi.com"
_TC_SERVICE = "iottav"
_TC_VERSION = "2019-11-26"
_TC_ACTION_STREAM = "DescribeLiveVideoChannel"
_TC_ACTION_SNAPSHOT = "GetThumbnail"
# Token cache lifetime (seconds) — Tencent STS tokens are valid ~2h; refresh after 1h
_TOKEN_TTL = 3600


@dataclass(frozen=True)
class AnycubicCameraEntityDescription(
    CameraEntityDescription, AnycubicCloudEntityDescription
):
    """Describes an Anycubic Cloud camera entity."""


CAMERA_TYPES: list[AnycubicCameraEntityDescription] = [
    AnycubicCameraEntityDescription(
        key="printer_camera",
        translation_key="printer_camera",
        printer_entity_type=PrinterEntityType.PRINTER,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anycubic Cloud camera entities."""
    coordinator: AnycubicCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    coordinator.add_entities_for_seen_printers(
        async_add_entities=async_add_entities,
        entity_constructor=AnycubicCloudCamera,
        platform=Platform.CAMERA,
        available_descriptors=list(CAMERA_TYPES),
    )


# ---------------------------------------------------------------------------
# Tencent Cloud TC3-HMAC-SHA256 signing helpers
# ---------------------------------------------------------------------------

def _tc3_sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _tc3_build_headers(
    secret_id: str,
    secret_key: str,
    session_token: str,
    region: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    """Return signed HTTP headers for a Tencent Cloud TC3-HMAC-SHA256 request."""
    timestamp = int(datetime.now(UTC).timestamp())
    date = datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")
    payload_str = json.dumps(payload, separators=(",", ":"))
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    canonical_headers = (
        f"content-type:application/json; charset=utf-8\n"
        f"host:{_TC_HOST}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "\n".join([
        "POST",
        "/",
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date}/{_TC_SERVICE}/tc3_request"
    string_to_sign = "\n".join([
        "TC3-HMAC-SHA256",
        str(timestamp),
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    signing_key_date = _tc3_sign(f"TC3{secret_key}".encode("utf-8"), date)
    signing_key_service = _tc3_sign(signing_key_date, _TC_SERVICE)
    signing_key_req = _tc3_sign(signing_key_service, "tc3_request")
    signature = hmac.new(
        signing_key_req,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": _TC_HOST,
        "X-TC-Action": action,
        "X-TC-Version": _TC_VERSION,
        "X-TC-Region": region,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Token": session_token,
    }


# ---------------------------------------------------------------------------
# Camera entity
# ---------------------------------------------------------------------------

class AnycubicCloudCamera(AnycubicCloudEntity, Camera):
    """Live-camera entity for an Anycubic Cloud printer."""

    entity_description: AnycubicCameraEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AnycubicCloudDataUpdateCoordinator,
        printer_id: int,
        entity_description: AnycubicCameraEntityDescription,
    ) -> None:
        """Initialise."""
        AnycubicCloudEntity.__init__(self, hass, coordinator, printer_id, entity_description)
        Camera.__init__(self)
        self._last_image: bytes | None = None
        self._raw_token: dict[str, Any] | None = None
        self._token_fetched_at: float = 0.0

    # ------------------------------------------------------------------
    # HA Camera interface
    # ------------------------------------------------------------------

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the most recent camera image."""
        try:
            await self._ensure_token()
            if self._raw_token is None:
                return self._last_image

            image = await self._fetch_snapshot()
            if image is not None:
                self._last_image = image
            return self._last_image
        except Exception as err:
            LOGGER.error("Anycubic camera image error for printer %s: %s", self._printer_id, err)
            return self._last_image

    async def stream_source(self) -> str | None:
        """Return the live-stream HLS URL if available."""
        try:
            await self._ensure_token()
            if self._raw_token is None:
                return None
            return await self._fetch_stream_url()
        except Exception as err:
            LOGGER.debug("Anycubic camera stream_source error: %s", err)
            return None

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    async def _ensure_token(self) -> None:
        """Refresh the Tencent Cloud STS token when it has expired."""
        if time.monotonic() - self._token_fetched_at < _TOKEN_TTL:
            return
        raw = await self.coordinator.async_request_camera_token(self._printer_id)
        if raw is not None:
            LOGGER.debug(
                "Anycubic camera token response for printer %s: %s",
                self._printer_id,
                json.dumps(raw),
            )
            self._raw_token = raw
            self._token_fetched_at = time.monotonic()
        else:
            LOGGER.warning(
                "Anycubic camera: could not obtain token for printer %s",
                self._printer_id,
            )
            self._raw_token = None

    def _extract_credentials(self) -> tuple[str, str, str, str, str] | None:
        """Return (secret_id, secret_key, session_token, region, device_tid) or None."""
        if self._raw_token is None:
            return None
        try:
            data: dict[str, Any] = self._raw_token.get("data", {})
            token_block: dict[str, Any] = data.get("token", {})
            secret_id: str = token_block.get("tmpSecretId", "")
            secret_key: str = token_block.get("tmpSecretKey", "")
            session_token: str = token_block.get("sessionToken", "")
            region: str = token_block.get("region", "ap-guangzhou")
            # msgid is our best guess for the Tencent IoT device Tid.
            # Log all keys so we can verify once tested against a real printer.
            device_tid: str = str(data.get("msgid", ""))
            LOGGER.debug(
                "Anycubic camera credentials extracted — "
                "region=%s tid=%s all_data_keys=%s",
                region,
                device_tid,
                list(data.keys()),
            )
            if not all([secret_id, secret_key, session_token, device_tid]):
                LOGGER.warning(
                    "Anycubic camera: incomplete credentials for printer %s "
                    "(missing fields). Raw data keys: %s",
                    self._printer_id,
                    list(data.keys()),
                )
                return None
            return secret_id, secret_key, session_token, region, device_tid
        except Exception as err:
            LOGGER.error("Anycubic camera: credential extraction failed: %s", err)
            return None

    # ------------------------------------------------------------------
    # Tencent Cloud IoT Video API calls
    # ------------------------------------------------------------------

    async def _tencent_post(
        self,
        action: str,
        payload: dict[str, Any],
        secret_id: str,
        secret_key: str,
        session_token: str,
        region: str,
    ) -> dict[str, Any] | None:
        """Make a signed POST request to the Tencent Cloud IoT Video API."""
        headers = _tc3_build_headers(
            secret_id=secret_id,
            secret_key=secret_key,
            session_token=session_token,
            region=region,
            action=action,
            payload=payload,
        )
        url = f"https://{_TC_HOST}/"
        body = json.dumps(payload, separators=(",", ":"))
        try:
            async with self.coordinator.anycubic_api._session.post(  # noqa: SLF001
                url,
                data=body,
                headers=headers,
            ) as resp:
                result: dict[str, Any] = await resp.json()
                LOGGER.debug("Tencent Cloud %s response: %s", action, json.dumps(result))
                return result
        except Exception as err:
            LOGGER.error("Tencent Cloud %s request failed: %s", action, err)
            return None

    async def _fetch_stream_url(self) -> str | None:
        """Ask Tencent Cloud IoT Video for a live-stream URL."""
        creds = self._extract_credentials()
        if creds is None:
            return None
        secret_id, secret_key, session_token, region, device_tid = creds

        resp = await self._tencent_post(
            action=_TC_ACTION_STREAM,
            payload={"Tid": device_tid},
            secret_id=secret_id,
            secret_key=secret_key,
            session_token=session_token,
            region=region,
        )
        if resp is None:
            return None

        response_body: dict[str, Any] = resp.get("Response", {})
        # Try common field names for HLS stream URLs
        for key in ("HlsUrl", "PlayUrl", "LiveUrl", "Url"):
            url = response_body.get(key)
            if url and isinstance(url, str):
                return url

        LOGGER.debug(
            "Anycubic camera: no stream URL found in %s response keys: %s",
            _TC_ACTION_STREAM,
            list(response_body.keys()),
        )
        return None

    async def _fetch_snapshot(self) -> bytes | None:
        """Ask Tencent Cloud IoT Video for a thumbnail image."""
        creds = self._extract_credentials()
        if creds is None:
            return None
        secret_id, secret_key, session_token, region, device_tid = creds

        resp = await self._tencent_post(
            action=_TC_ACTION_SNAPSHOT,
            payload={"Tid": device_tid},
            secret_id=secret_id,
            secret_key=secret_key,
            session_token=session_token,
            region=region,
        )
        if resp is None:
            return None

        response_body: dict[str, Any] = resp.get("Response", {})
        # Try to find a thumbnail URL
        for key in ("Url", "ThumbnailUrl", "ImageUrl", "SnapshotUrl"):
            thumb_url = response_body.get(key)
            if thumb_url and isinstance(thumb_url, str):
                return await self._download_image(thumb_url)

        # Try inline base64 image data
        for key in ("Data", "ImageData", "ThumbnailData"):
            b64: str | None = response_body.get(key)
            if b64 and isinstance(b64, str):
                import base64
                return base64.b64decode(b64)

        LOGGER.debug(
            "Anycubic camera: no snapshot found in %s response keys: %s",
            _TC_ACTION_SNAPSHOT,
            list(response_body.keys()),
        )
        return None

    async def _download_image(self, url: str) -> bytes | None:
        """Download image bytes from a URL."""
        try:
            async with self.coordinator.anycubic_api._session.get(url) as resp:  # noqa: SLF001
                if resp.status == 200:
                    return await resp.read()
                LOGGER.debug("Anycubic camera: image download returned HTTP %s", resp.status)
        except Exception as err:
            LOGGER.error("Anycubic camera: image download failed: %s", err)
        return None
