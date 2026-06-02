"""Google Drive INBOX watcher — polls a catch-all folder for new files.

Facundo or his team can drop files into a "Bandeja de entrada" folder
in Google Drive, and this watcher picks them up, feeds them through
the pipeline, and moves them to a "Procesados" subfolder.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from config import Settings
from drive_service import build_credentials, get_or_create_folder

logger = logging.getLogger(__name__)

# Files with these extensions are picked up from the INBOX
WATCHED_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".pdf", ".xlsx", ".xls"}
)


class DriveInboxWatcher:
    """Polls a Google Drive folder for new files and processes them."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        creds = build_credentials(settings.GOOGLE_DRIVE_CREDENTIALS)
        self.drive_service = build("drive", "v3", credentials=creds)
        self._processed_file_ids: set[str] = set()
        self._last_poll: str = ""

    async def poll(self) -> list[InboxFile]:
        """Poll the INBOX folder for new, unprocessed files.

        Returns a list of InboxFile objects ready for the processor.
        Files that have already been processed in this session are skipped.
        """
        inbox_id = self.settings.GOOGLE_DRIVE_INBOX_ID
        if not inbox_id:
            logger.warning("GOOGLE_DRIVE_INBOX_ID not set — skipping Drive INBOX poll")
            return []

        results: list[InboxFile] = []

        try:
            query = (
                f"'{inbox_id}' in parents "
                f"and mimeType != 'application/vnd.google-apps.folder' "
                f"and trashed = false"
            )
            resp = (
                self.drive_service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, createdTime)",
                    pageSize=50,
                    orderBy="createdTime asc",
                )
                .execute()
            )
        except HttpError as exc:
            logger.error("Drive INBOX poll failed: %s", exc)
            return results

        files = resp.get("files", [])
        self._last_poll = datetime.now(timezone.utc).isoformat()

        for f in files:
            file_id = f["id"]
            filename = f["name"]

            # Skip already-processed files
            if file_id in self._processed_file_ids:
                continue

            # Check extension
            ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
            if f".{ext}" not in WATCHED_EXTENSIONS:
                logger.debug("Skipping unsupported file in INBOX: %s", filename)
                self._processed_file_ids.add(file_id)  # don't retry
                continue

            # Download the file
            try:
                file_bytes = await self._download_file(file_id)
            except Exception:
                logger.exception("Failed to download %s from Drive INBOX", filename)
                continue

            # Move to "Procesados" subfolder
            try:
                await self._move_to_processed(file_id, filename)
            except Exception:
                logger.exception("Failed to move %s to Procesados", filename)
                # Don't block — file was downloaded, continue processing

            self._processed_file_ids.add(file_id)

            logger.info(
                "Drive INBOX: new file %s (%d bytes, %s)",
                filename,
                len(file_bytes),
                f["mimeType"],
            )

            results.append(
                InboxFile(
                    filename=filename,
                    content_type=f["mimeType"],
                    file_bytes=file_bytes,
                    drive_file_id=file_id,
                )
            )

        return results

    async def _download_file(self, file_id: str) -> bytes:
        """Download a file's content from Google Drive."""
        request = self.drive_service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    async def _move_to_processed(self, file_id: str, filename: str) -> None:
        """Move a processed file to the 'Procesados' subfolder."""
        inbox_id = self.settings.GOOGLE_DRIVE_INBOX_ID
        processed_id = await get_or_create_folder(
            self.drive_service, inbox_id, "Procesados"
        )

        # Add timestamp prefix to avoid name collisions
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{ts}_{filename}"

        try:
            # In Shared Drives, files can only have one parent.
            # addParents automatically replaces the existing parent (no
            # need for removeParents — would cause "cannotAddParent" error).
            self.drive_service.files().update(
                fileId=file_id,
                addParents=processed_id,
                body={"name": new_name},
                supportsAllDrives=True,
            ).execute()
        except HttpError as exc:
            raise RuntimeError(f"Drive move failed: {exc}") from exc


from dataclasses import dataclass


@dataclass
class InboxFile:
    """A file discovered in the Drive INBOX folder."""

    filename: str
    content_type: str
    file_bytes: bytes
    drive_file_id: str
