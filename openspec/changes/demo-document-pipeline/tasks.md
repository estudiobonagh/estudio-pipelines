# Implementation Tasks — Demo Document Pipeline

**Change ID:** `demo-document-pipeline`
**Date:** 2026-05-29

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,130 (12 files, all new) |
| 400-line budget risk | **High** — total well over 400 |
| Chained PRs recommended | **Yes** |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

---

## PR Chain Overview

| PR | Theme | Files | Est. lines | Depends on |
|----|-------|-------|------------|------------|
| **PR 1** | Foundation | `requirements.txt`, `.env.example`, `config.py`, `models.py`, `database.py`, `.gitignore` | ~320 | — |
| **PR 2** | Services | `whatsapp_service.py`, `classifier.py`, `drive_service.py` | ~390 | PR 1 |
| **PR 3** | Application | `processor.py`, `main.py` | ~360 | PR 2 |
| **PR 4** | Deployment | `Dockerfile`, `docker-compose.yml` | ~36 | PR 3 (loose) |

Each PR is autonomous: merges cleanly, doesn't break, and can be reviewed independently. PR 4 can ship in parallel with PR 3 since it only reads the final file set.

---

## PR 1 — Foundation: Config, Models, Database

### Task 1.1: External dependencies & env template

**Files:** `requirements.txt`, `.env.example`

**What:**
- Create `requirements.txt` with all dependencies from the design (Section 6):
  ```
  fastapi>=0.115.0
  uvicorn[standard]>=0.30.0
  httpx>=0.27.0
  openai>=1.30.0
  google-api-python-client>=2.130.0
  google-auth-httplib2>=0.2.0
  google-auth-oauthlib>=1.2.0
  twilio>=9.0.0
  sqlalchemy[asyncio]>=2.0.30
  aiosqlite>=0.20.0
  python-dotenv>=1.0.0
  pydantic>=2.7.0
  pydantic-settings>=2.3.0
  openpyxl>=3.1.0
  python-multipart>=0.0.9
  ```
- Create `.env.example` with all variables from the design (Section 7), placeholder values, and brief comments in Spanish.
- Add `*.db` and `data/` to `.gitignore`.

**Verification:**
- `pip install -r requirements.txt` succeeds in a clean venv.
- `.env.example` has all 10 variables (`TWILIO_*`, `XAI_API_KEY`, `GOOGLE_DRIVE_*`, `DATABASE_PATH`, `HOST`, `PORT`, `MAX_FILE_SIZE_MB`, `CLASSIFICATION_TIMEOUT_S`).
- `git status` does not track `*.db` or `data/`.

**Dependencies:** None. First task.

**Estimated lines:** ~55 (28 reqs + 20 env + 7 gitignore)

---

### Task 1.2: Configuration loader

**File:** `config.py`

**What:**
- Load settings from `.env` via `pydantic-settings` (or manual `python-dotenv` + `os.getenv` if `pydantic-settings` is unavailable).
- Define a `Settings` class/dataclass with all 14 fields (design Section: `config.py`).
- Validate required fields at load time: missing → `SystemExit(1)` with message `"Missing required environment variable: {VAR_NAME}"`.
- Validate `GOOGLE_DRIVE_CREDENTIALS` file existence: missing → `SystemExit(1)` with clear path in message.
- Provide a `load_settings()` function callable once at startup.
- All timeouts and limits come from env, not hardcoded.

**Verification:**
- Importing `config.py` without `.env` exits with code 1 and prints missing var.
- Importing with a valid `.env` returns a `Settings` object with all fields populated.
- `GOOGLE_DRIVE_CREDENTIALS` pointing to a nonexistent file fails with clear message.

**Dependencies:** Task 1.1 (needs `pydantic-settings` and `python-dotenv` installed).

**Estimated lines:** ~55

---

### Task 1.3: Data models & enums

**File:** `models.py`

**What:**
- Define `DocumentType` enum: `FACTURA`, `RECIBO`, `COMPROBANTE`, `EXTRACTO`, `OTRO` (design Section: `models.py`).
- Define `ProcessingStatus` enum with all 12 status values (design: `ProcessingStatus`).
- Define `ClassificationResult` Pydantic model: `cliente`, `tipo_documento`, `periodo`, `proveedor`, `monto`, `confianza` (confidence `ge=0.0, le=1.0`).
- Define `ProcessingRecord` Pydantic model with all 16 fields (design: `ProcessingRecord`). Note: this is a Pydantic representation, not the SQLAlchemy ORM class.
- Define `HealthCheck` model: `status`, `uptime_seconds`, `checks` dict.
- Define `StatsResponse` model: `total`, `successful`, `pending_review`, `failed`, `ignored`.

**Verification:**
- `ClassificationResult(confianza=1.5)` raises `ValidationError` (ge=0.0, le=1.0).
- `ClassificationResult(cliente="test", tipo_documento="Factura", periodo="05-2026", confianza=0.9)` validates successfully.
- All `ProcessingStatus` values are accessible as enum members.
- Models are importable with no external dependencies beyond `pydantic`.

**Dependencies:** Task 1.2 (conceptually independent, but co-located in PR 1).

**Estimated lines:** ~85

---

### Task 1.4: Database layer

**File:** `database.py`

**What:**
- Define SQLAlchemy ORM class `ProcessingLog` with all 16 columns (design Section: `database.py`):
  - `id` (Integer PK, autoincrement), `sender_phone`, `filename`, `media_content_type` (non-nullable Strings)
  - `classification_json` (nullable Text), `client_name`, `document_type`, `period` (nullable Strings)
  - `confidence` (nullable Float), `drive_file_id`, `drive_folder_path` (nullable Strings)
  - `status` (non-nullable String, default `"received"`), `error_message` (nullable Text)
  - `created_at`, `updated_at` (non-nullable Strings for ISO 8601)
- Implement `init_db(database_path: str)` — create async engine with `aiosqlite`, create tables, return `(engine, async_sessionmaker)`.
- Implement `create_log(session, **kwargs)` — insert new record.
- Implement `update_log(session, log_id, status, **extra_fields)` — update status + fields, set `updated_at`.
- Implement `get_stats(session)` — return dict with aggregate counts (total, successful=confirmation_sent, pending_review=low_confidence, failed=classification_failed+drive_error, ignored=ignored_*).
- Implement `check_duplicate(session, sender_phone, filename)` — query last 24h for same sender + filename.

**Verification:**
- `init_db(":memory:")` creates tables without error.
- Insert + update + query round-trip works: create a log, update status to `"stored"`, query confirms.
- `get_stats` returns correct counts with sample data.
- `check_duplicate` returns `True` for a record inserted <24h ago, `False` for unmatched.

**Dependencies:** Task 1.3 (uses `ProcessingStatus` enum for status values).

**Estimated lines:** ~130

---

## PR 2 — Service Layer: WhatsApp, Classifier, Drive

### Task 2.1: Twilio WhatsApp service

**File:** `whatsapp_service.py`

**What:**
- Define `ALLOWED_MEDIA_TYPES` as `frozenset` of 5 MIME types (design Section: `whatsapp_service.py`).
- Implement `validate_media_type(content_type: str) -> bool` — check against allowed set.
- Implement `normalize_phone(twilio_phone: str) -> str` — strip `whatsapp:` prefix from E.164 numbers (EC-004).
- Implement `async download_twilio_media(media_url, account_sid, auth_token) -> tuple[bytes, str]`:
  - Use `httpx.AsyncClient` with HTTP Basic Auth.
  - Check `Content-Length` header before download; reject if > `MAX_FILE_SIZE_MB * 1024 * 1024` (EC-002).
  - Return `(file_bytes, content_type)`. Raise specific exception on HTTP errors.
- Implement `async send_whatsapp_message(to_number, message, from_number, account_sid, auth_token) -> bool`:
  - Use Twilio SDK (`twilio.rest.Client`).
  - Return `True` on success, `False` on failure (caught `TwilioRestException`).

**Verification:**
- `normalize_phone("whatsapp:+5492664123456")` returns `"+5492664123456"`.
- `validate_media_type("image/jpeg")` returns `True`; `"video/mp4"` returns `False`.
- Download with invalid/expired Twilio URL raises an exception (manual test with real Twilio).
- Send function calls Twilio SDK correctly (mock test or manual with sandbox).

**Dependencies:** Task 1.2 (needs `Settings` for Twilio credentials and `MAX_FILE_SIZE_MB`).

**Estimated lines:** ~90

---

### Task 2.2: Grok AI classifier

**File:** `classifier.py`

**What:**
- Implement `async classify_document(file_bytes, content_type, filename, api_key, base_url, timeout_s) -> ClassificationResult`:
  - Create `AsyncOpenAI(base_url=base_url, api_key=api_key)` client.
  - For image types (`image/jpeg`, `image/png`): encode as base64 data URL in the message content array.
  - For PDF (`application/pdf`): encode as base64 data URL (same as image path).
  - For Excel (`.xlsx`, `.xls`): read with `openpyxl`, extract text, include in user prompt text.
  - Use Spanish classification prompt from the design.
  - Set `httpx.Timeout` on the OpenAI client to the configured timeout.
- Implement JSON response parsing:
  - Handle Grok responses wrapped in markdown code fences (` ```json ... ``` `).
  - Fall back to raw text JSON extraction if no fences.
  - Raise `ClassificationParseError` if response is not valid JSON.
- Define custom exceptions: `ClassificationTimeoutError`, `ClassificationAuthError`, `ClassificationParseError`.
- Log raw Grok response (truncated to 200 chars) on parse failure (REQ-CLASSIFY-003 scenario 4).

**Verification:**
- Valid image bytes produce a `ClassificationResult` with all fields (manual with Grok API key).
- JSON wrapped in ` ```json ``` ` fences is parsed correctly.
- Grok returning plain text (not JSON) raises `ClassificationParseError`.
- 401 from Grok raises `ClassificationAuthError`.
- 15-second timeout is enforced (mock slow endpoint).

**Dependencies:** Task 1.3 (needs `ClassificationResult` model), Task 1.2 (needs `Settings` for `CLASSIFICATION_TIMEOUT_S`).

**Estimated lines:** ~140

---

### Task 2.3: Google Drive service

**File:** `drive_service.py`

**What:**
- Define `MESES` lookup dict: `"01"` → `"Enero"` through `"12"` → `"Diciembre"` (EC-003).
- Define `DOCUMENT_TYPE_FOLDERS` lookup: singular → plural (e.g., `"Factura"` → `"Facturas"`).
- Implement `build_credentials(credentials_path: str)` — load service account JSON, return `Credentials` object.
- Implement `async get_or_create_folder(drive_service, parent_id, folder_name) -> str`:
  - Query for existing folder by name within parent (idempotent — EC-008).
  - Create only if not found. Return folder ID.
- Implement `async build_drive_path(drive_service, root_folder_id, client_name, period, document_type) -> str`:
  - Normalize `client_name` (strip, title case, collapse whitespace).
  - Parse `period` into month + year, map month to Spanish name.
  - Map `document_type` to plural folder name (fallback `"Otros"` for unknown types).
  - Handle special cases: low confidence → `_REVISION/`, failed classification → `_PENDIENTE/`, empty client → `Sin Clasificar/`.
  - Chain `get_or_create_folder` for each path segment.
  - Return leaf folder ID.
- Implement `construct_filename(period, document_type, proveedor, original_filename) -> str`:
  - Pattern: `{YYYY-MM}_{Tipo}_{Proveedor}_{original_filename}`.
  - Sanitize: replace spaces with `_`, strip invalid filename chars (`/\:*?"<>|`), limit `proveedor` to 50 chars, limit total to 200 chars.
- Implement `async upload_to_drive(drive_service, file_bytes, filename, folder_id, mime_type) -> str`:
  - Use `MediaIoBaseUpload` with `BytesIO(file_bytes)`.
  - Return Drive file ID on success.
  - Catch `googleapiclient.errors.HttpError` and raise descriptive exception.

**Verification:**
- `construct_filename("05-2026", "Factura", "EDESAL", "IMG-001.jpg")` → `"2026-05_Factura_EDESAL_IMG-001.jpg"`.
- `construct_filename("05-2026", "Recibo", "", "doc.pdf")` → `"2026-05_Recibo_doc.pdf"`.
- `get_or_create_folder` creates once, returns same ID on second call (idempotent).
- `build_drive_path` with `client_name=""` returns path under `Sin Clasificar/`.
- Upload succeeds with valid bytes and returns a non-empty file ID (manual with real Drive).

**Dependencies:** Task 1.2 (needs `Settings` for `GOOGLE_DRIVE_FOLDER_ID`).

**Estimated lines:** ~160

---

## PR 3 — Application: Pipeline Orchestrator + FastAPI App

### Task 3.1: Pipeline orchestrator

**File:** `processor.py`

**What:**
- Implement `async process_document(sender_phone, media_url, content_type, filename, settings, db_session) -> None`:
  - **Step 1:** Create DB log with `status="received"`.
  - **Step 2:** Validate media type; if unsupported → update DB `ignored_unsupported_type`, reply, return.
  - **Step 3:** Download media via `whatsapp_service.download_twilio_media()`.
    - File too large → update DB `download_failed`, reply, return.
    - Download HTTP error → update DB `download_failed`, reply, return.
  - **Step 4:** Update DB `status="classifying"`.
  - **Step 5:** Classify via `classifier.classify_document()`.
    - Timeout → update DB `classification_failed`, save to `_PENDIENTE/`, reply, return.
    - Auth error → update DB `classification_failed`, save to `_PENDIENTE/`, reply, return.
    - Parse error → update DB `classification_failed`, save to `_PENDIENTE/`, reply, return.
  - **Step 6:** Check confidence. If `< 0.5` → low confidence path (save to `_REVISION/`, reply, update DB `low_confidence`).
  - **Step 7:** Update DB `status="classified"` with classification fields.
  - **Step 8:** Build Drive path via `drive_service.build_drive_path()`. Handle special folders for low confidence and failed classification.
  - **Step 9:** Construct filename via `drive_service.construct_filename()`.
  - **Step 10:** Upload to Drive via `drive_service.upload_to_drive()`.
    - Quota/permission error → update DB `drive_error`, reply, return.
  - **Step 11:** Update DB `status="stored"` with Drive file ID and path.
  - **Step 12:** Send confirmation via `whatsapp_service.send_whatsapp_message()`.
    - Send failure → update DB `confirmation_failed` (file already saved, no retry).
  - **Step 13:** Update DB `status="confirmation_sent"`.
- Implement duplicate detection (EC-001): before processing, call `database.check_duplicate(sender_phone, filename)`. If match → reply `"📎 Ya recibimos este documento..."` and return.
- Implement edge cases:
  - Empty `periodo` from classifier → use current month (YYYY-MM).
  - Empty `cliente` → `"Sin Clasificar"` as folder name.
  - All user-facing messages in Spanish per design error handling table (Section 3).
- **Critical:** Wrap entire pipeline in try/except. Never let an unhandled exception bubble up. Log to DB with generic error status if truly unexpected.

**Verification:**
- Happy path: send a test document through the pipeline (via manual webhook or direct call). DB shows `received → classifying → classified → stored → confirmation_sent`.
- Low confidence (<0.5): file lands in `Clientes/_REVISION/`, DB shows `low_confidence`, user gets review message.
- Classifier failure: file lands in `Clientes/_PENDIENTE/`, DB shows `classification_failed`, user gets error message.
- Download failure: DB shows `download_failed`, user gets "no disponible" message.
- Drive failure: DB shows `drive_error`, user gets error message.
- Duplicate detection works (second identical send gets "ya recibimos" reply).

**Dependencies:** Tasks 2.1, 2.2, 2.3 (uses all three services), Tasks 1.2, 1.3, 1.4 (uses config, models, database).

**Estimated lines:** ~220

---

### Task 3.2: FastAPI application entry point

**File:** `main.py`

**What:**
- Create FastAPI app instance.
- Implement `lifespan` context manager:
  - On startup: `load_settings()`, `init_db()`, build Drive credentials, store in `app.state`.
  - On shutdown: close DB engine.
- **Route `POST /webhook`** (REQ-WEBHOOK-001):
  - Parse Twilio form data via `Request.form()` (not JSON — Twilio sends `application/x-www-form-urlencoded`).
  - Extract `From`, `MediaUrl0`, `MediaContentType0`.
  - If no media (text-only message) → reply with usage instructions in Spanish, log `ignored_no_media`, return 200.
  - Respond HTTP 200 immediately (within 3 seconds for Twilio).
  - Spawn background task: `asyncio.create_task(process_document(...))`.
  - Catch malformed payloads → return HTTP 400, log error, do not crash (REQ-WEBHOOK-001 scenario 4).
- **Route `GET /health`** (REQ-HEALTH-007):
  - Return `status`, `uptime_seconds`, `checks` dict.
  - Sub-checks: `twilio` (connectivity), `grok` (connectivity), `drive` (connectivity), `database` (accessibility).
  - Each sub-check has 3-second timeout. Failures → `status: "degraded"` with detail in `checks`.
- **Route `GET /stats`** (REQ-HEALTH-007 scenario 3):
  - Query `database.get_stats()`, return `StatsResponse`.
- Store `start_time` for uptime calculation.
- No authentication on webhook (demo only). Add `# TODO: Twilio signature validation for production`.

**Verification:**
- `GET /health` returns `{"status": "ok", ...}` with all checks passing (when APIs are reachable).
- `GET /health` returns `{"status": "degraded", "checks": {"grok": "unreachable"}}` when Grok is down.
- `GET /stats` returns correct aggregate counts from DB.
- `POST /webhook` with form data containing `MediaUrl0` returns 200 and spawns background task.
- `POST /webhook` with text-only payload returns 200 and polite Spanish reply.
- `POST /webhook` with malformed body returns 400, does not crash.

**Dependencies:** Task 3.1 (imports and calls `processor.process_document`), all prior tasks.

**Estimated lines:** ~140

---

## PR 4 — Docker Deployment

### Task 4.1: Dockerfile

**File:** `Dockerfile`

**What:**
- Base image: `python:3.12-slim`.
- Working directory: `/app`.
- Copy `requirements.txt`, run `pip install`.
- Copy all project files.
- Expose port 8000.
- CMD: `uvicorn main:app --host 0.0.0.0 --port 8000`.
- Follow the design Section 5 exactly.

**Verification:**
- `docker build -t demo-pipeline .` succeeds.
- Container starts and `GET /health` returns 200 (after `.env` is mounted or variables are set).

**Dependencies:** All code files from PR 3 exist. Loose dependency — can be created in parallel with PR 3.

**Estimated lines:** ~12

---

### Task 4.2: Docker Compose

**File:** `docker-compose.yml`

**What:**
- Service `pipeline` with `build: .`.
- Port mapping: `${PORT:-8000}:8000`.
- `env_file: .env`.
- Volumes:
  - `${GOOGLE_DRIVE_CREDENTIALS}:/app/credentials.json:ro`.
  - `./data:/app/data` (for SQLite persistence).
- `restart: unless-stopped`.
- Health check via Python one-liner hitting `/health`.
- Follow design Section 5 exactly.

**Verification:**
- `docker compose up` starts the service.
- `docker compose down && docker compose up` restarts with data surviving in `./data/`.
- Health check shows `healthy` in `docker compose ps`.

**Dependencies:** Task 4.1 (Dockerfile), `.env` file with valid credentials.

**Estimated lines:** ~24

---

## Task Summary Matrix

| Task | File(s) | Req(s) covered | Est. lines | PR |
|------|---------|----------------|------------|-----|
| 1.1 | `requirements.txt`, `.env.example`, `.gitignore` | REQ-CONFIG-008, REQ-DEPLOY-009 | ~55 | 1 |
| 1.2 | `config.py` | REQ-CONFIG-008 (all scenarios) | ~55 | 1 |
| 1.3 | `models.py` | REQ-CLASSIFY-003, REQ-DB-006, REQ-HEALTH-007 | ~85 | 1 |
| 1.4 | `database.py` | REQ-DB-006 (all scenarios) | ~130 | 1 |
| 2.1 | `whatsapp_service.py` | REQ-MEDIA-002, REQ-CONFIRM-005, EC-002, EC-004, EC-007 | ~90 | 2 |
| 2.2 | `classifier.py` | REQ-CLASSIFY-003 (all 5 scenarios) | ~140 | 2 |
| 2.3 | `drive_service.py` | REQ-DRIVE-004 (all 5 scenarios), EC-003, EC-008 | ~160 | 2 |
| 3.1 | `processor.py` | REQ-WEBHOOK-001, REQ-CLASSIFY-003, REQ-DRIVE-004, REQ-CONFIRM-005, EC-001 | ~220 | 3 |
| 3.2 | `main.py` | REQ-WEBHOOK-001 (all scenarios), REQ-HEALTH-007 (all scenarios) | ~140 | 3 |
| 4.1 | `Dockerfile` | REQ-DEPLOY-009 | ~12 | 4 |
| 4.2 | `docker-compose.yml` | REQ-DEPLOY-009 | ~24 | 4 |

---

## Delivery Notes

- **No existing files are modified.** All tasks create new files. Rollback is `rm` the new files.
- **PR 4 (Docker)** can ship in parallel with PR 3 since it only depends on the final file set existing, not on any runtime behavior.
- **Manual testing:** Each PR can be verified independently before merging the next:
  - PR 1: `config.py` loads successfully. `database.py` creates tables and runs CRUD in memory.
  - PR 2: Service functions tested individually with mock or real APIs.
  - PR 3: Full `uvicorn main:app` with `POST /webhook` via curl. Then end-to-end with Twilio Sandbox.
  - PR 4: `docker compose up` with valid `.env`.
- **Production readiness:** Not a concern for demo. All production concerns (auth, retries, Celery, Meta WhatsApp API) are explicitly deferred in the proposal.
