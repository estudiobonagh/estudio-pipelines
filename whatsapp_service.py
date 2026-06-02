"""Twilio WhatsApp integration — download media, send messages."""

from __future__ import annotations

import logging
from typing import Final

import httpx
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)

ALLOWED_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    [
        "image/jpeg",
        "image/png",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ]
)


class MediaDownloadError(Exception):
    """Raised when Twilio media download fails."""


class MediaTooLargeError(Exception):
    """Raised when the file exceeds the maximum allowed size."""


def validate_media_type(content_type: str) -> bool:
    """Check if the content type is in the allowed list."""
    return content_type in ALLOWED_MEDIA_TYPES


def normalize_phone(twilio_phone: str) -> str:
    """Strip 'whatsapp:' prefix from E.164 phone numbers.

    Example: 'whatsapp:+5492664123456' -> '+5492664123456'
    """
    return twilio_phone.removeprefix("whatsapp:")


async def download_twilio_media(
    media_url: str,
    account_sid: str,
    auth_token: str,
    max_size_bytes: int,
) -> tuple[bytes, str]:
    """Download media from a Twilio MediaUrl.

    Uses HTTP Basic Auth (Account SID as user, Auth Token as password).

    Returns (file_bytes, content_type).

    Raises:
        MediaTooLargeError: If Content-Length exceeds max_size_bytes.
        MediaDownloadError: If the download fails.
    """
    auth = httpx.BasicAuth(username=account_sid, password=auth_token)

    try:
        async with httpx.AsyncClient(auth=auth, timeout=10.0, follow_redirects=True) as client:
            # Check file size via HEAD request first
            head_response = await client.head(media_url)
            content_length = head_response.headers.get("Content-Length")
            if content_length and int(content_length) > max_size_bytes:
                raise MediaTooLargeError(
                    f"File size {content_length} bytes exceeds limit of "
                    f"{max_size_bytes} bytes ({max_size_bytes // (1024 * 1024)} MB)"
                )

            # Download the file
            response = await client.get(media_url)
            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", "application/octet-stream"
            )
            return response.content, content_type

    except httpx.HTTPStatusError as exc:
        raise MediaDownloadError(
            f"HTTP {exc.response.status_code} downloading media from Twilio"
        ) from exc
    except httpx.TimeoutException as exc:
        raise MediaDownloadError("Timeout downloading media from Twilio") from exc


async def send_whatsapp_message(
    to_number: str,
    message: str,
    from_number: str,
    account_sid: str,
    auth_token: str,
) -> bool:
    """Send a WhatsApp message via Twilio.

    Returns True on success, False on failure.
    """
    client = Client(account_sid, auth_token)

    try:
        msg = client.messages.create(
            from_=f"whatsapp:{from_number}",
            body=message,
            to=f"whatsapp:{to_number}",
        )
        logger.info(
            "WhatsApp message sent to %s, SID: %s",
            normalize_phone(to_number),
            msg.sid,
        )
        return True

    except TwilioRestException as exc:
        logger.error("Twilio send error to %s: %s", to_number, exc)
        return False
