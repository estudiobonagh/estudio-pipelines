# Technical Design — Demo Document Pipeline

**Change ID:** `demo-document-pipeline`
**Date:** 2026-05-29
**Status:** draft

---

## 1. Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       main.py                               │
│  FastAPI app, routes, lifespan, background tasks            │
│                                                             │
│  POST /webhook  →  processor.process_document() [bg task]   │
│  GET  /health   →  health check (all deps)                  │
│  GET  /stats    →  aggregate processing counts              │
└────────┬──────────────────┬──────────────┬──────────────────┘
         │                  │              │
    ┌────▼─────┐   ┌────────▼──────┐  ┌───▼──────────────┐
    │processor │   │  config.py    │  │  database.py     │
    │          │   │  .env loader  │  │  SQLite + SQLA   │
    │ orchestr │   │  validation   │  │  init / CRUD     │
    └─┬──┬──┬──┘   └───────────────┘  │  stats queries   │
      │  │  │                          └──────────────────┘
      │  │  └──────────────────────┐
      │  │                         │
┌─────▼──┐  ┌──────────────┐  ┌────▼─────────────┐
│whatsapp│  │ classifier.py│  │ drive_service.py │
│_service│  │              │  │                  │
│        │  │ Grok (xAI)   │  │ Google Drive API │
│download│  │ OpenAI compat│  │ folder create    │
│ send   │  │ structured   │  │ file upload      │
│ validate│ │ JSON prompt  │  │ path builder     │
└────────┘  └──────────────┘  └──────────────────┘

┌──────────────────────────────────────────┐
│              models.py                   │
│  Pydantic: WebhookPayload,              │
│  ClassificationResult, ProcessingLog,   │
│  HealthResponse, StatsResponse           │
└──────────────────────────────────────────┘
```

### Module responsibilities and interfaces

#### `main.py` — Application entry point

```python
# Lifespan: init DB on startup, no cleanup needed
# Routes:
@app.post("/webhook")  → async def twilio_webhook(request: Request)
@app.get("/health")    → async def health_check()
@app.get("/stats")     → async def processing_stats()
```

**Key decisions:**
- Twilio sends `application/x-www-form-urlencoded`, not JSON. FastAPI's `Request.form()` handles it.
- Webhook responds HTTP 200 immediately, then fires background task via `BackgroundTasks` or `asyncio.create_task`. Twilio timeout is 3 seconds.
- No authentication on webhook for demo (Twilio Sandbox is inherently low-risk). Add Twilio request signature validation for production.

#### `config.py` — Configuration management

```python
# Public API:
class Settings(BaseSettings):          # or manual .env parsing
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    XAI_API_KEY: str
    XAI_BASE_URL: str = "https://api.x.ai/v1"
    GOOGLE_DRIVE_CREDENTIALS: str
    GOOGLE_DRIVE_FOLDER_ID: str
    DATABASE_PATH: str = "processing.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    MAX_FILE_SIZE_MB: int = 15
    CLASSIFICATION_TIMEOUT_S: int = 15

def load_settings() -> Settings:      # reads .env, validates, returns
```

**Key decisions:**
- Use `pydantic-settings` if available, otherwise manual `os.getenv` + `python-dotenv`.
- Fail-fast: raise `SystemExit(1)` on missing required vars or missing credentials file.
- All timeouts and limits are configurable, not hardcoded.

#### `models.py` — Data models

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class DocumentType(str, Enum):
    FACTURA = "Factura"
    RECIBO = "Recibo"
    COMPROBANTE = "Comprobante"
    EXTRACTO = "Extracto"
    OTRO = "Otro"

class ClassificationResult(BaseModel):
    """What Grok returns — parsed and validated"""
    cliente: str
    tipo_documento: str                 # raw string; mapped to DocumentType later
    periodo: str                        # MM-YYYY
    proveedor: str = ""
    monto: float = 0.0
    confianza: float = Field(ge=0.0, le=1.0)

class ProcessingStatus(str, Enum):
    RECEIVED = "received"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    STORED = "stored"
    CONFIRMATION_SENT = "confirmation_sent"
    LOW_CONFIDENCE = "low_confidence"
    CLASSIFICATION_FAILED = "classification_failed"
    DOWNLOAD_FAILED = "download_failed"
    DRIVE_ERROR = "drive_error"
    IGNORED_NO_MEDIA = "ignored_no_media"
    IGNORED_UNSUPPORTED_TYPE = "ignored_unsupported_type"

class ProcessingRecord(BaseModel):
    """DB row representation"""
    id: Optional[int] = None
    sender_phone: str
    filename: str
    media_content_type: str
    classification_json: Optional[str] = None
    client_name: Optional[str] = None
    document_type: Optional[str] = None
    period: Optional[str] = None
    confidence: Optional[float] = None
    drive_file_id: Optional[str] = None
    drive_folder_path: Optional[str] = None
    status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: str                     # ISO 8601
    updated_at: str                     # ISO 8601

class HealthCheck(BaseModel):
    status: str                         # "ok" | "degraded"
    uptime_seconds: float
    checks: dict[str, str]              # e.g. {"twilio": "ok", "grok": "unreachable"}

class StatsResponse(BaseModel):
    total: int
    successful: int                     # confirmation_sent
    pending_review: int                 # low_confidence
    failed: int                         # classification_failed + drive_error
    ignored: int                        # ignored_*
```

#### `classifier.py` — Grok AI integration

```python
from openai import AsyncOpenAI

async def classify_document(
    file_bytes: bytes,
    content_type: str,
    filename: str,
    api_key: str,
    base_url: str = "https://api.x.ai/v1",
    timeout_s: int = 15,
) -> ClassificationResult:
    """Send document to Grok, return structured classification."""
```

**Implementation details:**

- Uses `openai` library with `AsyncOpenAI(base_url="https://api.x.ai/v1", api_key=...)`. Grok's API is OpenAI-compatible.
- Model: `grok-2-vision-1212` for images/PDFs (multimodal). For non-image files (Excel), use `grok-2-1212` with the file content as text in the system prompt.
- Prompt strategy: system prompt instructs Grok to return ONLY valid JSON in the ClassificationResult schema. User prompt contains the image/document.
- For images: encode as base64 data URL in the message content array.
- For PDFs: pass as base64 data URL with `application/pdf` MIME type. If Grok vision doesn't support PDF directly, each page is sent as an image (simplified for demo).
- For Excel: read with `openpyxl`, extract text content, include in the user prompt.
- Response parsing: extract JSON from the response. Handle cases where Grok wraps JSON in markdown code fences (` ```json ... ``` `). Fall back to raw text extraction.
- Timeout: 15-second `httpx.Timeout` on the OpenAI client.
- Errors: raise specific exceptions (`ClassificationTimeoutError`, `ClassificationAuthError`, `ClassificationParseError`).

**Prompt template (Spanish, structured):**

```
Eres un clasificador de documentos contables para un estudio en Argentina.
Analiza el documento adjunto y devuelve ÚNICAMENTE un JSON con esta estructura exacta:

{
  "cliente": "nombre del cliente o empresa",
  "tipo_documento": "Factura | Recibo | Comprobante | Extracto | Otro",
  "periodo": "MM-YYYY",
  "proveedor": "nombre del emisor si es visible",
  "monto": 0.00,
  "confianza": 0.0
}

Reglas:
- "confianza" debe ser un número entre 0.0 y 1.0 que refleje qué tan seguro estás de la clasificación.
- Si no podés determinar un campo, usá cadena vacía "" para textos y 0.00 para montos.
- El período se calcula a partir de la fecha visible en el documento. Si no hay fecha, usá "".
- No agregues texto fuera del JSON.
```

#### `whatsapp_service.py` — Twilio integration

```python
from twilio.rest import Client
import httpx

async def download_twilio_media(
    media_url: str,
    account_sid: str,
    auth_token: str,
) -> tuple[bytes, str]:
    """Download media from Twilio. Returns (file_bytes, content_type)."""

async def send_whatsapp_message(
    to_number: str,
    message: str,
    from_number: str,
    account_sid: str,
    auth_token: str,
) -> bool:
    """Send WhatsApp message via Twilio. Returns True on success."""

def validate_media_type(content_type: str) -> bool:
    """Check if content_type is in the allowed list."""

def normalize_phone(twilio_phone: str) -> str:
    """Strip 'whatsapp:' prefix from E.164 numbers."""

ALLOWED_MEDIA_TYPES = frozenset([
    "image/jpeg",
    "image/png",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
])
```

**Key decisions:**
- Media download uses `httpx` with HTTP Basic Auth (Account SID as user, Auth Token as password) — Twilio media URLs require this.
- Message sending uses the Twilio Python SDK (`twilio.rest.Client`). The SDK handles `whatsapp:` prefix automatically.
- The `From` number is always `TWILIO_WHATSAPP_NUMBER` (the Sandbox number).
- Response messages are template strings in Spanish. No i18n needed for demo.
- File size check: inspect `Content-Length` header before downloading; reject if > `MAX_FILE_SIZE_MB * 1024 * 1024`.

#### `drive_service.py` — Google Drive operations

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload

MESES = {
    "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
    "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
    "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
}

DOCUMENT_TYPE_FOLDERS = {
    "Factura": "Facturas",
    "Recibo": "Recibos",
    "Comprobante": "Comprobantes",
    "Extracto": "Extractos",
    "Otro": "Otros",
}

async def get_or_create_folder(
    drive_service,
    parent_id: str,
    folder_name: str,
) -> str:
    """Find existing folder by name under parent, or create it. Returns folder ID."""

async def build_drive_path(
    drive_service,
    root_folder_id: str,
    client_name: str,
    period: str,              # "MM-YYYY"
    document_type: str,
) -> str:
    """Ensure full folder hierarchy exists. Returns the leaf folder ID."""

async def upload_to_drive(
    drive_service,
    file_bytes: bytes,
    filename: str,
    folder_id: str,
    mime_type: str,
) -> str:
    """Upload file to the given folder. Returns Drive file ID."""

def construct_filename(
    period: str,              # "MM-YYYY" or "05-2026"
    document_type: str,
    proveedor: str,
    original_filename: str,
) -> str:
    """Build filename: {YYYY-MM}_{Tipo}_{Proveedor}_{original.ext}"""

def build_credentials(credentials_path: str):
    """Load service account credentials from JSON file."""
```

**Key decisions:**

- **Folder creation (idempotent):** `get_or_create_folder` queries Drive for folders with the exact name within the parent folder. Uses `q = name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false`. Creates only if not found.
- **Path construction:** `build_drive_path` chains `get_or_create_folder` calls for each level: root → `Clientes/` → `{cliente}/` → `{año}/` → `{MM - Mes}/` → `{tipo_plural}/`.
- **Fallback folders:**
  - Low confidence: `Clientes/_REVISION/{filename}`
  - Failed classification/processing: `Clientes/_PENDIENTE/{filename}`
- **Upload:** Uses `MediaIoBaseUpload` with `BytesIO` for in-memory bytes. Resumable upload disabled for simplicity (files are small).
- **Credentials:** Service account JSON file loaded once at startup via `config.py`. Path validated before Drive service is built.
- **Permissions:** Service account email must have "Editor" access on the root `GOOGLE_DRIVE_FOLDER_ID`. Documented as a setup step.

#### `processor.py` — Pipeline orchestrator

```python
async def process_document(
    sender_phone: str,
    media_url: str,
    content_type: str,
    filename: str,
    settings: Settings,
    db_session,                    # AsyncSession
) -> None:
    """
    Full pipeline: download → classify → store → confirm.
    Updates DB status at each step. Catches and handles all errors.
    """
```

**Pipeline state machine:**

```
received ──download──→ classifying ──Grok──→ classified ──Drive──→ stored ──Twilio──→ confirmation_sent
    │                      │                   │                    │
    └──download_failed     ├──classification_failed               └──drive_error
                           │  (→ save to _PENDIENTE/              (→ reply error)
                           │   → reply error)
                           │
                           └──low_confidence
                              (→ save to _REVISION/
                               → reply low_confidence)
```

**Error handling per stage:**

| Stage | Error type | DB status | Drive fallback | User reply |
|-------|-----------|-----------|----------------|------------|
| Download | HTTP error / timeout | `download_failed` | None (no file to save) | "⚠️ El archivo ya no está disponible…" |
| Download | File too large (>15MB) | `download_failed` | None | "📁 El archivo es muy grande…" |
| Classify | Grok timeout (15s) | `classification_failed` | `_PENDIENTE/` | "⏳ Estoy teniendo una demora…" |
| Classify | Grok auth error | `classification_failed` | `_PENDIENTE/` | "⚠️ Error interno…" |
| Classify | Non-JSON response | `classification_failed` | `_PENDIENTE/` | "⏳ Estoy teniendo una demora…" |
| Classify | Low confidence (<0.5) | `low_confidence` | `_REVISION/` | "📸 Recibí tu documento pero no pude clasificarlo…" |
| Drive | Quota / permissions | `drive_error` | None | "⚠️ Error al guardar tu documento…" |
| Confirm | Twilio send error | `confirmation_failed` | Already saved | None (already saved, no retry) |

**Duplicate detection (EC-001):**
- Check `sender_phone` + `filename` against recent DB records (last 24h). If match found with same media URL or same filename + similar timestamp, skip processing and reply "📎 Ya recibimos este documento."
- Not foolproof (different WhatsApp sessions may re-upload same file with different names), but catches accidental double-sends.

**Edge cases in processor:**
- If `periodo` is empty string from classifier, use current month as fallback.
- If `cliente` is empty, use "Sin Clasificar" as folder name.
- File bytes are never written to disk. All operations use `io.BytesIO`.

#### `database.py` — SQLite persistence

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Text, Integer

class Base(DeclarativeBase):
    pass

class ProcessingLog(Base):
    __tablename__ = "processing_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_phone: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    media_content_type: Mapped[str] = mapped_column(String, nullable=False)
    classification_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    period: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drive_file_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    drive_folder_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

# Functions:
async def init_db(database_path: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create engine, create tables, return engine + session factory."""

async def create_log(session: AsyncSession, **kwargs) -> ProcessingLog:
    """Insert new record with status='received', return the ORM object."""

async def update_log(
    session: AsyncSession,
    log_id: int,
    status: str,
    **extra_fields,
) -> None:
    """Update status and any extra fields. Sets updated_at to now."""

async def get_stats(session: AsyncSession) -> dict:
    """Return aggregate counts for /stats endpoint."""

async def check_duplicate(session: AsyncSession, sender_phone: str, filename: str) -> bool:
    """Check if same sender sent same filename in last 24 hours."""
```

**Key decisions:**
- SQLite via `aiosqlite` driver, not the default synchronous `pysqlite`. Required for async FastAPI without blocking the event loop.
- `String` columns for `created_at`/`updated_at` store ISO 8601 strings. No `DateTime` type needed — text is more portable and sufficient for the demo.
- No foreign keys, no indexes beyond primary key (demo scale — ~1000 records max).
- Database file path from `DATABASE_PATH` setting. Defaults to `./processing.db` in the working directory.
- Single session per request (FastAPI dependency injection pattern).

---

## 2. Data Flow

### Happy path (end-to-end)

```
1. Client sends WhatsApp → Twilio Sandbox
2. Twilio POSTs to ngrok URL → /webhook on FastAPI
3. main.py validates payload, extracts: From, MediaUrl0, MediaContentType0
4. Responds HTTP 200 immediately
5. Spawns background task: processor.process_document()
6. processor: db.create_log(status="received")
7. processor: whatsapp.download_twilio_media() → (bytes, content_type)
8. processor: classifier.classify_document(bytes, content_type, filename)
9. processor: db.update_log(status="classified", classification_json=..., client_name=..., etc.)
10. processor: drive.build_drive_path() → leaf_folder_id
11. processor: drive.upload_to_drive() → drive_file_id
12. processor: db.update_log(status="stored", drive_file_id=..., drive_folder_path=...)
13. processor: whatsapp.send_whatsapp_message() → confirmation
14. processor: db.update_log(status="confirmation_sent")
```

### Error paths (graceful degradation)

```
Download fails → db.update_log(status="download_failed") → reply error → stop
Classify fails  → save to _PENDIENTE/ → db.update_log(status="classification_failed") → reply error
Low confidence  → save to _REVISION/  → db.update_log(status="low_confidence") → reply info
Drive fails     → db.update_log(status="drive_error") → reply error → stop
Confirm fails   → db.update_log(status="confirmation_failed") → already saved, no retry
```

### Background task lifecycle

- Processor runs as `asyncio.create_task(process_document(...))`. It has no timeout — runs until completion or error.
- If the server restarts mid-processing, the task is lost. Document is partially processed but no DB record was committed. This is acceptable for the demo.
- For production, use a proper job queue (Celery/Redis). Explicitly deferred.

---

## 3. Error Handling Strategy

### Philosophy: fail gracefully, never crash

| Layer | Strategy |
|-------|----------|
| Webhook | Catch all in route handler. Return 200 for Twilio, log error. Never 500 for invalid input — Twilio would retry. |
| Processor | Catch all exceptions. Update DB with error status. Reply to user. Never let exception propagate unhandled. |
| External APIs | All calls have explicit timeouts. Catch `httpx.TimeoutException`, `googleapiclient.errors.HttpError`, `twilio.base.exceptions.TwilioRestException`. |
| Database | Wraps session operations in try/except. DB errors are logged but don't block reply. |
| Startup | Fail-fast for config errors. Try/except for health check endpoints — return "degraded" with details. |

### Timeout configuration

| Operation | Timeout | Rationale |
|-----------|---------|-----------|
| Twilio media download | 10s | Media files are <15MB. Should complete quickly. |
| Grok classification | 15s | AI inference can take a few seconds. |
| Drive folder queries | 5s | Simple list/search operations. |
| Drive file upload | 15s | Uploading a <15MB file. |
| Twilio message send | 5s | API call, very fast in practice. |
| Health check sub-checks | 3s each | Quick connectivity checks. |

### Retry policy

**No retries in the demo.** Rationale:
- Twilio retries webhooks if we don't respond in time (our 200 response is immediate, so this is handled).
- User can resend a failed document manually (simple, user-driven retry).
- Adding retry logic with exponential backoff adds complexity without proportional value for a demo.
- Production should add retries for Drive uploads and confirmation sends.

---

## 4. Google Drive Folder Structure

### Path construction algorithm

```
Input: root_folder_id, client_name, period ("MM-YYYY"), document_type

1. Normalize client_name: strip, title case, collapse whitespace
2. Parse period: month = period[0:2], year = period[3:7]
3. Map month number to Spanish name via MESES lookup
4. Map document_type to plural folder name via DOCUMENT_TYPE_FOLDERS lookup
5. Path segments: ["Clientes", client_name, year, f"{month} - {month_name}", folder_plural]
6. For each segment: get_or_create_folder(parent_id, segment_name)
7. Return leaf folder ID
```

### Special folders

| Condition | Target folder | Purpose |
|-----------|--------------|---------|
| Classification confidence < 0.5 | `Clientes/_REVISION/` | Manual review by Facundo |
| Classification failed / API error | `Clientes/_PENDIENTE/` | System couldn't process, needs attention |
| client_name empty from classifier | `Clientes/Sin Clasificar/{year}/{month_path}/` | No client identified |

### File naming convention

```
Pattern: {YYYY-MM}_{Tipo}_{Proveedor}_{original_filename}

Example inputs:
  period="05-2026", tipo="Factura", proveedor="EDESAL", original="IMG-20260529-WA0001.jpg"
  → "2026-05_Factura_EDESAL_IMG-20260529-WA0001.jpg"

  period="05-2026", tipo="Recibo", proveedor="", original="documento.pdf"
  → "2026-05_Recibo_documento.pdf"

Sanitization:
- Replace spaces in proveedor with underscores
- Strip special characters that are invalid in filenames: / \ : * ? " < > |
- Limit proveedor to 50 chars
- Limit total filename to 200 chars
```

---

## 5. Docker Setup

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps if needed (none for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml`

```yaml
services:
  pipeline:
    build: .
    ports:
      - "${PORT:-8000}:8000"
    env_file:
      - .env
    volumes:
      # Mount service account key as read-only
      - ${GOOGLE_DRIVE_CREDENTIALS}:/app/credentials.json:ro
      # Mount SQLite DB to persist across restarts
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"]
      interval: 30s
      timeout: 5s
      retries: 3
```

**Key decisions:**
- `.env` loaded from `env_file`. The `GOOGLE_DRIVE_CREDENTIALS` variable inside `.env` should point to `/app/credentials.json` (the internal container path), while the volume mount maps the host path.
- SQLite DB stored in `/app/data/` which is mounted as a volume. Survives container restarts.
- `restart: unless-stopped` ensures the service comes back after crashes or host reboots.
- Health check uses a simple HTTP call. Does not require installing curl in the container.

### Ngrok for local development

Not containerized — run separately:
```bash
ngrok http 8000
```
Copy the ngrok URL (e.g., `https://abc123.ngrok.io`) into Twilio Console as the Sandbox webhook URL. With free tier, this URL changes every 2 hours. Document this operational step.

---

## 6. Dependencies (`requirements.txt`)

```
# Web framework
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# HTTP client (Twilio media download, health checks)
httpx>=0.27.0

# AI classification (OpenAI-compatible client for Grok)
openai>=1.30.0

# Google Drive
google-api-python-client>=2.130.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.2.0

# WhatsApp via Twilio
twilio>=9.0.0

# Database
sqlalchemy[asyncio]>=2.0.30
aiosqlite>=0.20.0

# Configuration
python-dotenv>=1.0.0

# Data validation
pydantic>=2.7.0
pydantic-settings>=2.3.0

# File processing
openpyxl>=3.1.0         # Excel file reading
python-multipart>=0.0.9 # FastAPI form data parsing
```

**Note:** `google-auth-oauthlib` is required by `google-api-python-client` even for service account auth (dependency of the library, not for OAuth flow).

---

## 7. `.env.example`

```env
# Twilio Sandbox
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=+14155238886

# Grok (xAI)
XAI_API_KEY=xai-your-key-here

# Google Drive
GOOGLE_DRIVE_CREDENTIALS=./service-account-key.json
GOOGLE_DRIVE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j

# Database
DATABASE_PATH=./data/processing.db

# Server
HOST=0.0.0.0
PORT=8000

# Limits
MAX_FILE_SIZE_MB=15
CLASSIFICATION_TIMEOUT_S=15
```

---

## 8. Testing Strategy

For the demo, testing is manual (end-to-end with Twilio Sandbox). However, the code structure supports unit testing:

| Module | Test approach | Mock strategy |
|--------|--------------|---------------|
| `config.py` | Unit test settings loading, missing vars, file validation | No mocks needed |
| `models.py` | Unit test Pydantic validation (valid/invalid ClassificationResult) | No mocks needed |
| `classifier.py` | Unit test JSON parsing (mock OpenAI client responses) | Mock `AsyncOpenAI` |
| `drive_service.py` | Unit test path construction, filename sanitization | Mock `googleapiclient` |
| `whatsapp_service.py` | Unit test phone normalization, media type validation | Mock `httpx` and `twilio.rest.Client` |
| `processor.py` | Integration test with mocked dependencies | Mock all three services |
| `database.py` | Unit test CRUD operations, stats queries | Real SQLite in-memory |
| `main.py` | Integration test webhook endpoint | FastAPI `TestClient` |

Tests are **not required** for the demo milestone but the architecture supports them when the project graduates beyond demo.

---

## 9. File Manifest (all new files)

```
estudio-pipelines/
├── main.py                    # FastAPI app
├── config.py                  # .env loading + validation
├── models.py                  # Pydantic models
├── classifier.py              # Grok integration
├── drive_service.py           # Google Drive operations
├── whatsapp_service.py        # Twilio integration
├── processor.py               # Pipeline orchestrator
├── database.py                # SQLite + SQLAlchemy
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container build
├── docker-compose.yml         # Local / VPS deployment
├── .env.example               # Environment template
├── .gitignore                 # (updated: add .env, data/, __pycache__, *.pyc)
└── docs/                      # Existing — unchanged
    ├── canales-entrada.md
    ├── demo-setup.md
    ├── flujo-de-datos.md
    ├── plan-facundo.md
    └── stack-tecnologico.md
```

**No existing files are modified.** Only new files are created.

---

## 10. Design Decisions Log

| Decision | Rationale | Alternatives considered |
|----------|-----------|------------------------|
| Async everywhere | FastAPI is async-native. Twilio SDK sync calls wrapped in `asyncio.to_thread`. | Sync-only would be simpler but blocks the event loop on I/O. |
| `openai` library for Grok | Grok's API is OpenAI-compatible. Mature library, well-tested. | Direct `httpx` calls. Rejected: more boilerplate, no streaming/tool support (not needed now, but future-proof). |
| SQLAlchemy + aiosqlite vs raw sqlite3 | SQLAlchemy provides ORM convenience, async support via aiosqlite, and migration path to PostgreSQL. | Raw `aiosqlite`. Rejected: more boilerplate for CRUD, no ORM benefits. |
| No retry logic | Demo simplicity. User-driven retry (resend the WhatsApp message). | Tenacity/backoff. Rejected: adds complexity without proportional demo value. Deferred to production. |
| BytesIO for in-memory file handling | No temp files on disk. Simpler cleanup, more secure (no sensitive data on disk). | `tempfile.NamedTemporaryFile`. Rejected: requires cleanup, potential data leak on crash. |
| Service account for Drive | No user OAuth flow. One-time setup. | OAuth 2.0 user consent. Rejected: requires web UI, refresh token management. Overkill for server-to-server. |
| `pydantic-settings` for config | Typed, validated, autocomplete-friendly. De facto standard for FastAPI projects. | Manual `os.getenv`. Rejected: no validation, no type safety. |
| No auth on webhook | Twilio Sandbox is low-risk. Production adds Twilio signature validation. | HMAC signature validation. Deferred: adds setup complexity for demo testers. |
