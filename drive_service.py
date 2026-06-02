"""Google Drive operations — folder creation, file upload, path building."""

from __future__ import annotations

import io
import logging
import re
from typing import Final

from google.auth.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

# Spanish month names for folder hierarchy
MESES: Final[dict[str, str]] = {
    "01": "Enero",
    "02": "Febrero",
    "03": "Marzo",
    "04": "Abril",
    "05": "Mayo",
    "06": "Junio",
    "07": "Julio",
    "08": "Agosto",
    "09": "Septiembre",
    "10": "Octubre",
    "11": "Noviembre",
    "12": "Diciembre",
}

# Map singular document types to plural folder names
DOCUMENT_TYPE_FOLDERS: Final[dict[str, str]] = {
    "Factura": "Facturas",
    "Recibo": "Recibos",
    "Comprobante": "Comprobantes",
    "Extracto": "Extractos",
    "Otro": "Otros",
}

# Characters invalid in Google Drive file/folder names
_INVALID_NAME_CHARS = re.compile(r'[/\\:*?"<>|]')


class DriveError(Exception):
    """Base exception for Google Drive operations."""


class DriveQuotaError(DriveError):
    """Drive quota exceeded."""


class DrivePermissionError(DriveError):
    """Insufficient permissions for the operation."""


def build_credentials(source: str | dict) -> Credentials:
    """Load service account credentials from a JSON key file or dict.

    Accepts either a file path to a service account JSON, or the parsed
    JSON dict directly (for Railway/cloud where files aren't practical).
    """
    scopes = ["https://www.googleapis.com/auth/drive"]
    if isinstance(source, dict):
        return service_account.Credentials.from_service_account_info(
            source, scopes=scopes
        )
    return service_account.Credentials.from_service_account_file(
        source, scopes=scopes
    )


def _sanitize_name(name: str, max_length: int = 200) -> str:
    """Remove invalid characters and trim to max_length."""
    cleaned = _INVALID_NAME_CHARS.sub("_", name)
    return cleaned[:max_length].strip()


async def get_or_create_folder(
    drive_service,
    parent_id: str,
    folder_name: str,
) -> str:
    """Find an existing folder by name under parent, or create it.

    Idempotent: returns the same folder ID on repeated calls.
    """
    # Escape single quotes in folder name for the Drive query
    safe_name = folder_name.replace("'", "\\'")

    query = (
        f"name = '{safe_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed = false"
    )

    try:
        results = (
            drive_service.files()
            .list(q=query, fields="files(id, name)", pageSize=1,
                  supportsAllDrives=True, includeItemsFromAllDrives=True)
            .execute()
        )
    except HttpError as exc:
        raise DriveError(f"Drive query failed for '{folder_name}': {exc}") from exc

    files = results.get("files", [])
    if files:
        return files[0]["id"]

    # Create the folder
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }

    try:
        folder = (
            drive_service.files()
            .create(body=folder_metadata, fields="id", supportsAllDrives=True)
            .execute()
        )
    except HttpError as exc:
        _handle_drive_http_error(exc, f"creating folder '{folder_name}'")
        raise  # unreachable — _handle_drive_http_error always raises

    return folder["id"]


async def build_drive_path(
    drive_service,
    root_folder_id: str,
    client_name: str,
    period: str,
    document_type: str,
) -> str:
    """Ensure the full folder hierarchy exists. Returns the leaf folder ID.

    Path: Clientes / {client_name} / {year} / {MM} - {MonthName} / {TypePlural}

    Special cases:
    - Empty client_name → "Sin Clasificar"
    - Unknown document_type → "Otros"
    - Empty period → uses current month/year
    """
    # Normalize client name
    client = _sanitize_name(client_name.strip().title(), max_length=100)
    if not client:
        client = "Sin Clasificar"

    # Build top-level "Clientes" folder
    clientes_id = await get_or_create_folder(drive_service, root_folder_id, "Clientes")

    # Client folder
    cliente_id = await get_or_create_folder(drive_service, clientes_id, client)

    # Parse period (MM-YYYY, M-YYYY, MM-YY) or fall back to current
    if period and len(period) >= 6 and "-" in period:
        parts = period.split("-")
        month_num = parts[0].zfill(2)
        year = parts[1]
    else:
        from datetime import datetime

        now = datetime.now()
        month_num = now.strftime("%m")
        year = now.strftime("%Y")

    month_name = MESES.get(month_num, month_num)

    # Year folder
    year_id = await get_or_create_folder(drive_service, cliente_id, year)

    # Month folder: "05 - Mayo"
    month_label = f"{month_num} - {month_name}"
    month_id = await get_or_create_folder(drive_service, year_id, month_label)

    # Document type folder (plural)
    type_folder = DOCUMENT_TYPE_FOLDERS.get(document_type, "Otros")
    type_id = await get_or_create_folder(drive_service, month_id, type_folder)

    return type_id


def construct_filename(
    period: str,
    document_type: str,
    proveedor: str,
    original_filename: str,
) -> str:
    """Build a standardized filename.

    Pattern: {YYYY-MM}_{Tipo}_{Proveedor}_{original}

    Sanitization:
    - Replaces spaces with underscores
    - Strips invalid filename characters
    - Limits proveedor to 50 chars
    - Limits total to 200 chars
    """
    # Parse date prefix
    if period and len(period) >= 6 and "-" in period:
        parts = period.split("-")
        month = parts[0].zfill(2)
        date_prefix = f"{parts[1]}-{month}"
    else:
        from datetime import datetime

        date_prefix = datetime.now().strftime("%Y-%m")

    # Sanitize document type
    tipo = _sanitize_name(document_type.replace(" ", "_"), max_length=30) or "Documento"

    # Sanitize proveedor
    prov = (
        _sanitize_name(proveedor.replace(" ", "_"), max_length=50)
        if proveedor
        else ""
    )

    # Sanitize original filename
    original = _sanitize_name(original_filename.replace(" ", "_"), max_length=80)

    # Build filename
    if prov:
        filename = f"{date_prefix}_{tipo}_{prov}_{original}"
    else:
        filename = f"{date_prefix}_{tipo}_{original}"

    # Truncate to 200 chars, preserving extension
    if len(filename) > 200:
        name_part, _, ext = filename.rpartition(".")
        max_name = 200 - len(ext) - 1
        filename = f"{name_part[:max_name]}.{ext}"

    return filename


async def upload_to_drive(
    drive_service,
    file_bytes: bytes,
    filename: str,
    folder_id: str,
    mime_type: str,
) -> str:
    """Upload a file to a Google Drive folder. Returns the Drive file ID."""
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype=mime_type,
        resumable=False,
    )

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    try:
        uploaded = (
            drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
    except HttpError as exc:
        _handle_drive_http_error(exc, f"uploading '{filename}'")
        raise  # unreachable — _handle_drive_http_error always raises

    file_id = uploaded.get("id", "")
    logger.info("Uploaded '%s' to Drive folder %s, file ID: %s", filename, folder_id, file_id)
    return file_id


def _handle_drive_http_error(exc: HttpError, context: str) -> None:
    """Map Drive HTTP errors to specific exceptions."""
    status = exc.resp.status if hasattr(exc, "resp") else 0
    if status == 403:
        raise DrivePermissionError(
            f"Permission denied {context}. Is the service account shared on the Drive folder?"
        ) from exc
    if status == 429:
        raise DriveQuotaError(
            f"Drive quota exceeded {context}"
        ) from exc
    raise DriveError(f"Drive API error {context}: {exc}") from exc
