"""Pipeline orchestrator — ties WhatsApp, classifier, Drive, and DB together.

All user-facing messages are in Spanish (the client's language).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from classifier import (
    ClassificationAuthError,
    ClassificationError,
    ClassificationParseError,
    ClassificationTimeoutError,
    classify_document,
)
from config import Settings
from database import check_duplicate, create_log, update_log
from drive_service import (
    DriveError,
    build_drive_path,
    construct_filename,
    upload_to_drive,
)
from models import ProcessingStatus
from whatsapp_service import (
    MediaDownloadError,
    MediaTooLargeError,
    download_twilio_media,
    send_whatsapp_message,
    validate_media_type,
)

logger = logging.getLogger(__name__)

# Minimum confidence threshold for automatic filing
LOW_CONFIDENCE_THRESHOLD = 0.5

# Spanish user-facing messages
MSG_DUPLICATE = (
    "📎 Ya recibimos este documento anteriormente. "
    "Si necesitás reenviarlo, por favor avisanos."
)
MSG_UNSUPPORTED_TYPE = (
    "⚠️ El tipo de archivo que enviaste no está soportado. "
    "Por favor enviá fotos (JPG/PNG), PDFs o archivos Excel."
)
MSG_FILE_TOO_LARGE = (
    "📁 El archivo es muy grande (máximo 15 MB). "
    "Por favor enviá una versión más chica o comprimida."
)
MSG_DOWNLOAD_FAILED = (
    "⚠️ El archivo ya no está disponible. "
    "Por favor volvé a enviarlo."
)
MSG_CLASSIFY_TIMEOUT = (
    "⏳ Estoy teniendo una demora procesando tu documento. "
    "Por favor volvé a intentarlo en unos minutos."
)
MSG_CLASSIFY_FAILED = (
    "⚠️ Error interno al procesar tu documento. "
    "El equipo del estudio lo va a revisar manualmente."
)
MSG_LOW_CONFIDENCE = (
    "📸 Recibí tu documento pero no pude clasificarlo automáticamente. "
    "El equipo del estudio lo va a revisar."
)
MSG_DRIVE_ERROR = (
    "⚠️ Error al guardar tu documento. "
    "Por favor avisale al estudio así lo revisan."
)
MSG_SUCCESS_TEMPLATE = (
    "Hola {cliente}, recibimos tu {tipo} del período {periodo}. "
    "Queda registrada en tu carpeta."
)
MSG_SUCCESS_NO_CLIENT = (
    "✅ Recibimos tu documento. Queda registrado."
)


async def process_document(
    sender_phone: str,
    media_url: str,
    content_type: str,
    filename: str,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    preloaded_bytes: bytes | None = None,
    skip_confirmation: bool = False,
) -> None:
    """Full document processing pipeline.

    Steps: validate → download → classify → store → confirm.
    Updates DB status at each step. Never raises — all errors are caught.
    Creates its own DB session so the caller can return immediately.

    If preloaded_bytes is provided (email, Drive INBOX), the download
    step is skipped.
    """
    log_id = 0  # sentinel — set after Step 1
    file_bytes: bytes | None = preloaded_bytes
    classification = None

    db_session = session_factory()
    try:
        # --- Step 0: Duplicate check ---
        is_dup = await check_duplicate(db_session, sender_phone, filename)
        if is_dup:
            logger.info("Duplicate detected: %s from %s", filename, sender_phone)
            await send_whatsapp_message(
                sender_phone,
                MSG_DUPLICATE,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            return

        # --- Step 1: Create log ---
        record = await create_log(
            db_session,
            sender_phone=sender_phone,
            filename=filename,
            media_content_type=content_type,
        )
        log_id = record.id

        # --- Step 2: Validate media type ---
        if not validate_media_type(content_type):
            await update_log(
                db_session,
                log_id,
                ProcessingStatus.IGNORED_UNSUPPORTED_TYPE.value,
            )
            await send_whatsapp_message(
                sender_phone,
                MSG_UNSUPPORTED_TYPE,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            return

        # --- Step 3: Download (skip if preloaded) ---
        if file_bytes is not None:
            # Bytes provided directly (email, Drive INBOX)
            effective_content_type = content_type
        else:
            max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
            try:
                file_bytes, actual_content_type = await download_twilio_media(
                    media_url,
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                    max_size_bytes=max_bytes,
                )
            except MediaTooLargeError:
                await update_log(
                    db_session,
                    log_id,
                    ProcessingStatus.DOWNLOAD_FAILED.value,
                    error_message="File too large",
                )
                await send_whatsapp_message(
                    sender_phone,
                    MSG_FILE_TOO_LARGE,
                    settings.TWILIO_WHATSAPP_NUMBER,
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                )
                return
            except MediaDownloadError as exc:
                await update_log(
                    db_session,
                    log_id,
                    ProcessingStatus.DOWNLOAD_FAILED.value,
                    error_message=str(exc),
                )
                await send_whatsapp_message(
                    sender_phone,
                    MSG_DOWNLOAD_FAILED,
                    settings.TWILIO_WHATSAPP_NUMBER,
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                )
                return

            effective_content_type = actual_content_type or content_type

        # At this point download succeeded — file_bytes is guaranteed to be set
        assert file_bytes is not None

        # --- Step 4: Classify ---
        await update_log(
            db_session, log_id, ProcessingStatus.CLASSIFYING.value
        )

        try:
            classification = await classify_document(
                file_bytes=file_bytes,
                content_type=effective_content_type,
                filename=filename,
                api_key=settings.XAI_API_KEY,
                base_url=settings.XAI_BASE_URL,
                model=settings.XAI_MODEL,
                timeout_s=settings.CLASSIFICATION_TIMEOUT_S,
            )
        except ClassificationTimeoutError as exc:
            await _handle_classification_failure(
                db_session, log_id, settings, sender_phone,
                file_bytes, filename, effective_content_type, str(exc),
                MSG_CLASSIFY_TIMEOUT,
            )
            return
        except ClassificationAuthError as exc:
            await _handle_classification_failure(
                db_session, log_id, settings, sender_phone,
                file_bytes, filename, effective_content_type, str(exc),
                MSG_CLASSIFY_FAILED,
            )
            return
        except ClassificationParseError as exc:
            await _handle_classification_failure(
                db_session, log_id, settings, sender_phone,
                file_bytes, filename, effective_content_type, str(exc),
                MSG_CLASSIFY_FAILED,
            )
            return
        except ClassificationError as exc:
            await _handle_classification_failure(
                db_session, log_id, settings, sender_phone,
                file_bytes, filename, effective_content_type, str(exc),
                MSG_CLASSIFY_FAILED,
            )
            return

        classification_json = classification.model_dump_json()

        # --- Step 5: Check confidence ---
        if classification.confianza < LOW_CONFIDENCE_THRESHOLD:
            await update_log(
                db_session,
                log_id,
                ProcessingStatus.LOW_CONFIDENCE.value,
                classification_json=classification_json,
                client_name=classification.cliente,
                document_type=classification.tipo_documento,
                period=classification.periodo,
                confidence=classification.confianza,
            )
            # Save to _REVISION folder
            try:
                rev_path = await build_drive_path(
                    drive_service=_get_drive_service(settings),
                    root_folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
                    client_name="_REVISION",
                    period=classification.periodo or _current_period(),
                    document_type=classification.tipo_documento or "Otro",
                )
                await upload_to_drive(
                    drive_service=_get_drive_service(settings),
                    file_bytes=file_bytes,
                    filename=filename,
                    folder_id=rev_path,
                    mime_type=effective_content_type,
                )
            except DriveError:
                logger.exception("Failed to save low-confidence doc to _REVISION")

            await send_whatsapp_message(
                sender_phone,
                MSG_LOW_CONFIDENCE,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            return

        # --- Step 6: Update as classified ---
        await update_log(
            db_session,
            log_id,
            ProcessingStatus.CLASSIFIED.value,
            classification_json=classification_json,
            client_name=classification.cliente,
            document_type=classification.tipo_documento,
            period=classification.periodo,
            confidence=classification.confianza,
        )

        # --- Step 7: Build filename ---
        constructed_filename = construct_filename(
            period=classification.periodo,
            document_type=classification.tipo_documento,
            proveedor=classification.proveedor,
            original_filename=filename,
        )

        # --- Step 8: Build Drive path ---
        client_for_path = classification.cliente or "Sin Clasificar"
        try:
            drive_path = await build_drive_path(
                drive_service=_get_drive_service(settings),
                root_folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
                client_name=client_for_path,
                period=classification.periodo,
                document_type=classification.tipo_documento,
            )
        except DriveError as exc:
            await update_log(
                db_session,
                log_id,
                ProcessingStatus.DRIVE_ERROR.value,
                error_message=str(exc),
            )
            await send_whatsapp_message(
                sender_phone,
                MSG_DRIVE_ERROR,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            return

        # --- Step 9: Upload to Drive ---
        try:
            drive_file_id = await upload_to_drive(
                drive_service=_get_drive_service(settings),
                file_bytes=file_bytes,
                filename=constructed_filename,
                folder_id=drive_path,
                mime_type=effective_content_type,
            )
        except DriveError as exc:
            await update_log(
                db_session,
                log_id,
                ProcessingStatus.DRIVE_ERROR.value,
                error_message=str(exc),
            )
            await send_whatsapp_message(
                sender_phone,
                MSG_DRIVE_ERROR,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )
            return

        # --- Step 10: Update as stored ---
        await update_log(
            db_session,
            log_id,
            ProcessingStatus.STORED.value,
            drive_file_id=drive_file_id,
            drive_folder_path=f"Clientes/{client_for_path}/{classification.periodo}/{classification.tipo_documento}",
        )

        # --- Step 11: Send confirmation (WhatsApp only) ---
        if not skip_confirmation:
            if classification.cliente:
                confirm_msg = MSG_SUCCESS_TEMPLATE.format(
                    cliente=classification.cliente,
                    tipo=classification.tipo_documento or "documento",
                    periodo=classification.periodo or "actual",
                )
            else:
                confirm_msg = MSG_SUCCESS_NO_CLIENT

            sent = await send_whatsapp_message(
                sender_phone,
                confirm_msg,
                settings.TWILIO_WHATSAPP_NUMBER,
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
            )

            if sent:
                await update_log(
                    db_session,
                    log_id,
                    ProcessingStatus.CONFIRMATION_SENT.value,
                )
            else:
                logger.warning(
                    "Confirmation send failed for log_id=%d, file already stored",
                    log_id,
                )
        else:
            await update_log(
                db_session,
                log_id,
                ProcessingStatus.CONFIRMATION_SENT.value,
            )

    except Exception:
        # Catch-all: log unexpected errors, don't crash
        logger.exception(
            "Unexpected error processing document from %s: %s",
            sender_phone,
            filename,
        )
        if log_id != 0:
            try:
                await update_log(
                    db_session,
                    log_id,
                    ProcessingStatus.CLASSIFICATION_FAILED.value,
                    error_message="Unexpected internal error",
                )
            except Exception:
                logger.exception("Failed to update log on unexpected error")
    finally:
        await db_session.close()


async def _handle_classification_failure(
    db_session: AsyncSession,
    log_id: int,
    settings: Settings,
    sender_phone: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    error_detail: str,
    user_message: str,
) -> None:
    """Handle classification failure: update DB, save to _PENDIENTE, reply."""
    await update_log(
        db_session,
        log_id,
        ProcessingStatus.CLASSIFICATION_FAILED.value,
        error_message=error_detail,
    )

    # Try to save the raw file to _PENDIENTE so nothing is lost
    try:
        drive_path = await build_drive_path(
            drive_service=_get_drive_service(settings),
            root_folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
            client_name="_PENDIENTE",
            period=_current_period(),
            document_type="Otro",
        )
        await upload_to_drive(
            drive_service=_get_drive_service(settings),
            file_bytes=file_bytes,
            filename=filename,
            folder_id=drive_path,
            mime_type=content_type,
        )
    except DriveError:
        logger.exception("Failed to save failed-classification doc to _PENDIENTE")

    await send_whatsapp_message(
        sender_phone,
        user_message,
        settings.TWILIO_WHATSAPP_NUMBER,
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
    )


def _current_period() -> str:
    """Return current month-year as MM-YYYY."""
    return datetime.now().strftime("%m-%Y")


# Module-level cache for Drive service
_drive_service_cache = None
_drive_settings_hash = None


def _get_drive_service(settings: Settings):
    """Get or create a cached Google Drive service instance."""
    global _drive_service_cache, _drive_settings_hash

    current_hash = hash(settings.GOOGLE_DRIVE_CREDENTIALS)
    if _drive_service_cache is not None and _drive_settings_hash == current_hash:
        return _drive_service_cache

    from drive_service import build_credentials
    from googleapiclient.discovery import build

    credentials = build_credentials(settings.GOOGLE_DRIVE_CREDENTIALS)
    _drive_service_cache = build("drive", "v3", credentials=credentials)
    _drive_settings_hash = current_hash
    return _drive_service_cache
