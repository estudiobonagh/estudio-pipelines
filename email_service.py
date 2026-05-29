"""Email document reception — IMAP polling for inbound attachments.

Polls an IMAP inbox periodically for unseen messages with attachments,
downloads them, and feeds them into the processor pipeline.
"""

from __future__ import annotations

import email
from dataclasses import dataclass
from email import header as email_header
from email.message import Message
import logging
import mimetypes
from typing import Optional

import aioimaplib

logger = logging.getLogger(__name__)


class IMAPLoginError(Exception):
    """Raised when IMAP authentication fails."""


ALLOWED_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".xls"}
)


@dataclass
class EmailAttachment:
    """A single attachment extracted from an email."""

    sender_email: str
    filename: str
    content_type: str
    file_bytes: bytes
    message_id: str
    subject: str


class EmailPoller:
    """Polls an IMAP inbox for new messages with attachments."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    async def fetch_new_attachments(self) -> list[EmailAttachment]:
        """Connect via IMAP, find unseen messages with attachments, download them.

        Returns a list of EmailAttachment objects ready for the processor.
        Marks processed messages as seen.
        """
        attachments: list[EmailAttachment] = []

        imap = aioimaplib.IMAP4_SSL(self.host, self.port)

        try:
            await imap.wait_hello_from_server()

            login_status, login_data = await imap.login(
                self.username, self.password
            )
            if login_status != "OK":
                raise IMAPLoginError(
                    f"IMAP login failed for {self.username}: "
                    f"{login_data!r}"
                )
            logger.info("IMAP login successful for %s", self.username)

            await imap.select("INBOX")

            # Search for unseen messages
            status, messages = await imap.search("UNSEEN")
            if status != "OK" or not messages[0]:
                return attachments

            message_ids = messages[0].split()
            logger.info("IMAP: %d unseen messages found", len(message_ids))

            for raw_msg_id in message_ids:
                try:
                    msg_id = raw_msg_id.decode()
                    attachment = await self._process_message(imap, msg_id)
                    if attachment is not None:
                        attachments.append(attachment)
                    # Mark as seen
                    await imap.store(msg_id, "+FLAGS", "\\Seen")
                except Exception:
                    logger.exception(
                        "Failed to process IMAP message %s", msg_id
                    )

        except Exception:
            logger.exception("IMAP polling failed for %s", self.username)
        finally:
            try:
                await imap.logout()
            except Exception:
                pass

        return attachments

    async def _process_message(
        self,
        imap: aioimaplib.IMAP4_SSL,
        msg_id: str,
    ) -> Optional[EmailAttachment]:
        """Fetch and parse a single IMAP message, extracting the first attachment."""
        status, data = await imap.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None

        raw_email = data[1] if isinstance(data[1], bytes) else data[0]  # type: ignore[index]
        if not isinstance(raw_email, bytes):
            return None

        msg = email.message_from_bytes(raw_email)

        # Extract sender
        sender = _extract_sender(msg)
        subject = str(msg.get("Subject", ""))
        message_id_header = str(msg.get("Message-ID", msg_id))

        # Walk through message parts looking for attachments
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in content_disposition:
                continue

            filename = part.get_filename()
            if filename is None:
                continue

            # Decode RFC 2047 encoded filenames
            filename = _decode_header(filename)

            # Check extension
            ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
            if f".{ext}" not in ALLOWED_EXTENSIONS and ext:
                logger.debug("Skipping unsupported attachment: %s", filename)
                continue

            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue

            content_type = part.get_content_type()
            if content_type == "application/octet-stream" and ext:
                content_type, _ = mimetypes.guess_type(filename)
                content_type = content_type or "application/octet-stream"

            logger.info(
                "Email attachment: %s from %s (%d bytes)",
                filename,
                sender,
                len(payload),
            )

            return EmailAttachment(
                sender_email=sender,
                filename=filename,
                content_type=content_type,
                file_bytes=payload,
                message_id=message_id_header,
                subject=subject,
            )

        return None


def _extract_sender(msg: Message) -> str:
    """Extract the sender's email address from a message."""
    from_header = str(msg.get("From", ""))
    # Try to extract email from "Name <email>" format
    if "<" in from_header and ">" in from_header:
        start = from_header.index("<") + 1
        end = from_header.index(">")
        return from_header[start:end].strip()
    return from_header.strip()


def _decode_header(value: str) -> str:
    """Decode RFC 2047 encoded header values."""
    decoded_parts: list[str] = []
    for part, charset in email_header.decode_header(value):
        if isinstance(part, bytes):
            try:
                decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded_parts.append(part.decode("utf-8", errors="replace"))
        else:
            decoded_parts.append(str(part))
    return "".join(decoded_parts)
