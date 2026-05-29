"""FastAPI application — webhook endpoints, health check, stats."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from config import load_settings
from database import create_log, get_stats as db_get_stats
from database import init_db
from models import HealthCheck, ProcessingStatus, StatsResponse
from processor import process_document
from whatsapp_service import normalize_phone, send_whatsapp_message

logger = logging.getLogger(__name__)

# Module-level state
start_time: float = 0.0
settings = None
session_factory = None
db_engine = None

# Spanish usage instructions for text-only WhatsApp messages
USAGE_MSG = (
    "👋 ¡Hola! Soy el asistente virtual del estudio contable.\n\n"
    "Podés enviarme fotos de facturas, comprobantes, recibos, "
    "PDFs o archivos Excel y los clasifico automáticamente.\n\n"
    "Simplemente adjuntá el documento a este chat y envialo. "
    "Te confirmo cuando quede registrado."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, init DB. Shutdown: close engine."""
    global start_time, settings, session_factory, db_engine

    # Startup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting document pipeline...")

    settings = load_settings()
    logger.info("Settings loaded successfully")

    db_engine, session_factory = await init_db(settings.DATABASE_PATH)
    logger.info("Database initialized at %s", settings.DATABASE_PATH)

    start_time = time.monotonic()
    logger.info("Pipeline ready. Listening on %s:%d", settings.HOST, settings.PORT)

    # --- Background channel pollers ---
    background_tasks: list[asyncio.Task[None]] = []

    # Email IMAP poller (only if configured)
    if settings.EMAIL_IMAP_HOST:
        task = asyncio.create_task(
            _email_poll_loop(settings, session_factory)
        )
        background_tasks.append(task)
        logger.info(
            "Email poller started: %s:%d every %ds",
            settings.EMAIL_IMAP_HOST,
            settings.EMAIL_IMAP_PORT,
            settings.EMAIL_POLL_INTERVAL_S,
        )

    # Drive INBOX poller (only if configured)
    if settings.GOOGLE_DRIVE_INBOX_ID:
        task = asyncio.create_task(
            _drive_inbox_poll_loop(settings, session_factory)
        )
        background_tasks.append(task)
        logger.info(
            "Drive INBOX poller started for folder %s",
            settings.GOOGLE_DRIVE_INBOX_ID,
        )

    yield

    # Shutdown — cancel background pollers
    for task in background_tasks:
        task.cancel()
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
        logger.info("Background pollers stopped")

    if db_engine:
        await db_engine.dispose()
        logger.info("Database connection closed")


app = FastAPI(
    title="Estudio Pipelines — Document Reception",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> HealthCheck:
    """Health check with dependency verification."""
    uptime = time.monotonic() - start_time
    checks: dict[str, str] = {}

    if settings is None:
        return HealthCheck(
            status="degraded",
            uptime_seconds=uptime,
            checks={"startup": "not initialized"},
        )

    # Check Twilio connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                "https://api.twilio.com",
                auth=httpx.BasicAuth(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                ),
            )
            checks["twilio"] = "ok" if resp.status_code < 500 else "degraded"
    except Exception:
        checks["twilio"] = "unreachable"

    # Check Grok connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.XAI_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.XAI_API_KEY}"},
            )
            checks["grok"] = "ok" if resp.status_code < 500 else "degraded"
    except Exception:
        checks["grok"] = "unreachable"

    # Check Drive connectivity
    try:
        from drive_service import build_credentials
        from googleapiclient.discovery import build

        creds = build_credentials(settings.GOOGLE_DRIVE_CREDENTIALS)
        drive_svc = build("drive", "v3", credentials=creds)
        drive_svc.files().list(pageSize=1).execute()
        checks["drive"] = "ok"
    except Exception:
        checks["drive"] = "unreachable"

    # Check database
    try:
        if session_factory is not None:
            async with session_factory() as session:
                await db_get_stats(session)
            checks["database"] = "ok"
        else:
            checks["database"] = "not initialized"
    except Exception:
        checks["database"] = "unreachable"

    all_ok = all(v == "ok" or v == "not initialized" for v in checks.values())
    status = "ok" if all_ok else "degraded"

    return HealthCheck(status=status, uptime_seconds=uptime, checks=checks)


@app.get("/stats")
async def processing_stats() -> StatsResponse:
    """Return aggregate processing statistics."""
    if session_factory is None:
        return StatsResponse(total=0, successful=0, pending_review=0, failed=0, ignored=0)

    async with session_factory() as session:
        stats = await db_get_stats(session)

    return StatsResponse(**stats)


@app.post("/webhook")
async def twilio_webhook(request: Request):
    """Receive incoming WhatsApp messages from Twilio.

    Twilio sends application/x-www-form-urlencoded, not JSON.
    We respond 200 immediately and process in the background.
    """
    if settings is None or session_factory is None:
        return JSONResponse(
            {"status": "error", "message": "Server not initialized"},
            status_code=503,
        )

    try:
        form_data = await request.form()
    except Exception:
        logger.warning("Malformed webhook payload from %s", request.client)
        return JSONResponse(
            {"status": "error", "message": "Invalid form data"},
            status_code=400,
        )

    # Extract Twilio fields
    from_number = form_data.get("From", "")
    media_url = form_data.get("MediaUrl0", "")
    media_content_type = form_data.get("MediaContentType0", "")
    num_media = int(str(form_data.get("NumMedia", "0")))

    # Normalize phone number
    sender_phone = normalize_phone(str(from_number))

    # No media attached — text-only message
    if num_media == 0 or not media_url:
        logger.info("Text-only message from %s, ignoring", sender_phone)
        # Insert a log record for the ignored message
        async with session_factory() as session:
            await create_log(
                session,
                sender_phone=sender_phone,
                filename="text-only",
                media_content_type="text/plain",
                status=ProcessingStatus.IGNORED_NO_MEDIA.value,
            )

        # Reply with usage instructions
        await send_whatsapp_message(
            sender_phone,
            USAGE_MSG,
            settings.TWILIO_WHATSAPP_NUMBER,
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )

        return PlainTextResponse(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
            media_type="application/xml",
        )

    # Generate a filename for the incoming media

    media_type_str = str(media_content_type)
    if "pdf" in media_type_str:
        ext = ".pdf"
    elif "excel" in media_type_str or "spreadsheet" in media_type_str:
        ext = ".xlsx"
    elif "image" in media_type_str:
        ext = ".jpg"
    else:
        ext = ".bin"

    filename = f"{uuid.uuid4().hex[:8]}{ext}"

    logger.info(
        "Webhook received from %s: %s (%s)",
        sender_phone,
        filename,
        media_content_type,
    )

    # Respond to Twilio immediately (within 3 seconds)
    # Then spawn background task for the pipeline
    # Pass session_factory so the task creates its own session
    asyncio.create_task(
        process_document(
            sender_phone=sender_phone,
            media_url=str(media_url),
            content_type=media_type_str,
            filename=filename,
            settings=settings,
            session_factory=session_factory,
        )
    )

    # Twilio expects XML or 200 OK. Empty <Response> means don't reply via TwiML.
    return PlainTextResponse(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
        media_type="application/xml",
    )


# --- Background channel pollers ---


async def _email_poll_loop(settings, session_factory) -> None:
    """Background task: poll IMAP inbox for new email attachments."""

    from email_service import EmailPoller, IMAPLoginError

    poller = EmailPoller(
        host=settings.EMAIL_IMAP_HOST,
        port=settings.EMAIL_IMAP_PORT,
        username=settings.EMAIL_IMAP_USERNAME,
        password=settings.EMAIL_IMAP_PASSWORD,
    )

    while True:
        try:
            attachments = await poller.fetch_new_attachments()
            for att in attachments:
                logger.info(
                    "Email poller: processing %s from %s",
                    att.filename,
                    att.sender_email,
                )
                asyncio.create_task(
                    process_document(
                        sender_phone=att.sender_email,
                        media_url="",
                        content_type=att.content_type,
                        filename=att.filename,
                        settings=settings,
                        session_factory=session_factory,
                        preloaded_bytes=att.file_bytes,
                        skip_confirmation=True,
                    )
                )
        except asyncio.CancelledError:
            logger.info("Email poller cancelled")
            break
        except IMAPLoginError:
            logger.error(
                "Email poller: login failed — check EMAIL_IMAP_USERNAME/PASSWORD. "
                "Retrying in %ds",
                settings.EMAIL_POLL_INTERVAL_S * 10,
            )
            await asyncio.sleep(settings.EMAIL_POLL_INTERVAL_S * 10)
            continue
        except Exception:
            logger.exception("Email poller iteration failed")

        await asyncio.sleep(settings.EMAIL_POLL_INTERVAL_S)


async def _drive_inbox_poll_loop(settings, session_factory) -> None:
    """Background task: poll Drive INBOX folder for new files."""

    from drive_watcher import DriveInboxWatcher

    watcher = DriveInboxWatcher(settings)

    while True:
        try:
            files = await watcher.poll()
            for f in files:
                logger.info(
                    "Drive INBOX: processing %s (%d bytes)",
                    f.filename,
                    len(f.file_bytes),
                )
                asyncio.create_task(
                    process_document(
                        sender_phone="drive-inbox",
                        media_url="",
                        content_type=f.content_type,
                        filename=f.filename,
                        settings=settings,
                        session_factory=session_factory,
                        preloaded_bytes=f.file_bytes,
                        skip_confirmation=True,
                    )
                )
        except asyncio.CancelledError:
            logger.info("Drive INBOX poller cancelled")
            break
        except Exception:
            logger.exception("Drive INBOX poller iteration failed")

        await asyncio.sleep(60)  # poll every 60 seconds
