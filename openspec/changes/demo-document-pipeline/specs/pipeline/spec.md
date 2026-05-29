# Pipeline Specification — Demo Document Pipeline

## Purpose

Define the required behavior for the demo document reception and classification pipeline. The system receives accounting documents via WhatsApp (Twilio Sandbox), classifies them with AI (Grok), stores them in Google Drive under a structured folder hierarchy, confirms receipt to the sender, and logs all processing activity.

This is the first executable artifact of **Etapa 1, Fase 1A** (Recepción unificada) from the Facundo Bona plan.

## Requirements

### REQ-WEBHOOK-001: Receive WhatsApp webhook from Twilio

The system MUST expose an HTTP POST endpoint that accepts incoming WhatsApp message webhooks from Twilio Sandbox.

The system MUST respond with HTTP 200 within 3 seconds of receiving the webhook (Twilio timeout) to prevent retries, even if downstream processing continues asynchronously.

The system SHALL validate that the incoming request contains a message with a media attachment (image, document, or audio). Text-only messages MUST be acknowledged with a polite reply instructing the sender to attach a document.

#### Scenario: Client sends a photo via WhatsApp

- GIVEN a client has joined the Twilio Sandbox with the join code
- AND the Twilio webhook URL is configured in the Twilio Console
- WHEN the client sends a photo of a factura to the Sandbox number via WhatsApp
- THEN the system receives an HTTP POST at `/webhook` with the Twilio payload
- AND the system extracts the sender's phone number (`From`) and media URL (`MediaUrl0`)
- AND the system responds with HTTP 200 within 3 seconds
- AND the system begins async processing of the media

#### Scenario: Client sends a PDF via WhatsApp

- GIVEN the webhook endpoint is live
- WHEN the client sends a PDF document
- THEN the system extracts `MediaUrl0` and `MediaContentType0` from the payload
- AND recognizes it as a document (not an image)
- AND begins processing

#### Scenario: Client sends a text-only message (no media)

- GIVEN the webhook endpoint is live
- WHEN the client sends a text message with no attachment to the Sandbox number
- THEN the system replies: "👋 ¡Hola! Enviame una foto, PDF o Excel del comprobante y lo clasifico automáticamente. Si necesitás hablar con Facundo, escribile a su número personal."
- AND the system does NOT attempt classification
- AND the message is logged in the database with `status = 'ignored_no_media'`

#### Scenario: Malformed webhook payload

- GIVEN the webhook endpoint is live
- WHEN the system receives a POST with an unexpected payload structure
- THEN the system responds with HTTP 400
- AND logs the error with the raw payload (truncated to 500 chars) for debugging
- AND does NOT crash

---

### REQ-MEDIA-002: Download media from Twilio

The system MUST download attached media files from Twilio's temporary media URLs before they expire.

The system MUST authenticate with Twilio's API using `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` from environment variables.

The system SHALL support the following media types:
- `image/jpeg` — photos of documents
- `image/png` — screenshots / scanned images
- `application/pdf` — PDF documents
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — Excel files
- `application/vnd.ms-excel` — legacy Excel files

#### Scenario: Successful download of a JPEG image

- GIVEN a webhook payload containing `MediaUrl0` pointing to a JPEG file at Twilio
- WHEN the system attempts to download the media
- THEN the file is downloaded as bytes within 5 seconds
- AND the content type matches `image/jpeg`
- AND the file bytes are passed to the classifier

#### Scenario: Media URL has expired

- GIVEN a webhook payload with a `MediaUrl0` that has already expired (Twilio media URLs expire after 4 hours)
- WHEN the system attempts to download
- THEN Twilio returns HTTP 404
- AND the system logs the error with `status = 'download_failed_expired'`
- AND the system replies to the sender: "⚠️ El archivo ya no está disponible. ¿Podés reenviarlo? ¡Gracias!"
- AND the system does NOT crash

#### Scenario: Unsupported media type

- GIVEN a webhook payload with `MediaContentType0: video/mp4`
- WHEN the system identifies the content type
- THEN the system does NOT attempt download
- AND the system replies: "📎 Por ahora solo recibo fotos, PDFs y archivos de Excel. ¿Podés mandarlo en uno de esos formatos?"
- AND logs the event with `status = 'ignored_unsupported_type'`

---

### REQ-CLASSIFY-003: Classify document with Grok AI

The system MUST send the downloaded document to the Grok API (xAI) for classification.

The system MUST use the OpenAI-compatible API endpoint provided by xAI (`https://api.x.ai/v1`).

The classification prompt MUST instruct Grok to return structured JSON with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `cliente` | string | Name of the client the document belongs to |
| `tipo_documento` | enum | `Factura`, `Recibo`, `Comprobante`, `Extracto`, `Otro` |
| `periodo` | string | Period in `MM-YYYY` format |
| `proveedor` | string | Name of the issuer/supplier if identifiable |
| `monto` | number | Monetary amount detected in the document, 0.00 if not found |
| `confianza` | number | Self-reported confidence between 0.0 and 1.0 |

The system MUST handle Grok API responses that contain valid JSON but with unexpected field names by mapping them to the expected schema where possible.

The system SHALL set a timeout of 15 seconds for the Grok API call.

#### Scenario: Grok successfully classifies a factura

- GIVEN a PDF of an electricity bill from "EDESAL" for client "María López" dated May 2026
- WHEN the system sends the PDF to Grok with the classification prompt
- THEN Grok returns valid JSON with `tipo_documento: "Factura"`, `cliente: "María López"`, `periodo: "05-2026"`, `proveedor: "EDESAL"`, `monto` matching the bill total, and `confianza >= 0.8`
- AND the classification result is passed to the Drive storage module

#### Scenario: Grok returns low confidence classification

- GIVEN a blurry photo of a handwritten note
- WHEN Grok classifies the image
- THEN Grok returns `confianza < 0.5`
- AND the system logs the low-confidence result
- AND the file is still saved to Drive, but under `Clientes/_REVISION/` instead of the client folder
- AND the system replies: "📸 Recibí tu documento pero no pude clasificarlo con seguridad. Facundo lo va a revisar. ¡Gracias!"

#### Scenario: Grok API timeout

- GIVEN the Grok API is slow to respond
- WHEN the 15-second timeout is exceeded
- THEN the system catches the timeout exception
- AND logs the error with `status = 'classification_timeout'`
- AND saves the file to `Clientes/_PENDIENTE/` on Drive
- AND replies: "⏳ Estoy teniendo una demora procesando tu documento. Lo guardé para revisión manual. ¡Gracias por la paciencia!"

#### Scenario: Grok API returns non-JSON response

- GIVEN Grok returns a text response that is not valid JSON
- WHEN the system attempts to parse the response
- THEN the system logs the raw response (truncated to 200 chars)
- AND falls back to saving the file to `Clientes/_PENDIENTE/`
- AND replies with the same pending-review message as above

#### Scenario: Grok API authentication failure

- GIVEN the `XAI_API_KEY` is invalid or expired
- WHEN the system calls Grok
- THEN Grok returns HTTP 401
- AND the system logs the authentication error
- AND saves the file to `Clientes/_PENDIENTE/`
- AND replies to the sender: "⚠️ Error interno. El equipo ya fue notificado. ¡Gracias!"

---

### REQ-DRIVE-004: Store document in Google Drive

The system MUST store classified documents in Google Drive under the following folder hierarchy:

```
Clientes/{cliente}/{año}/{MM - Mes}/{tipo_documento}/{archivo}
```

Where:
- `{cliente}` matches the client name from classification, normalized (trimmed, title case)
- `{año}` is the year extracted from `periodo` (e.g., `2026`)
- `{MM - Mes}` is the month number and Spanish name (e.g., `05 - Mayo`)
- `{tipo_documento}` is the plural form of the document type (e.g., `Facturas`, `Recibos`)
- `{archivo}` follows the naming pattern: `{YYYY-MM}_{Tipo}_{Proveedor}_{original_filename}`

The system MUST create intermediate folders if they do not exist (idempotent folder creation).

The system MUST authenticate with Google Drive using a service account JSON key file whose path is configured in `GOOGLE_DRIVE_CREDENTIALS`.

The root folder for all client documents MUST be configurable via `GOOGLE_DRIVE_FOLDER_ID`.

#### Scenario: New document for an existing client folder

- GIVEN folder `Clientes/Maria Lopez/2026/05 - Mayo/Facturas/` already exists in Drive
- WHEN the system saves a new factura for "María López" from May 2026
- THEN the system does NOT create duplicate folders
- AND uploads the file to the existing `Facturas/` folder
- AND the file is named `2026-05_Factura_EDESAL_foto123.jpeg`

#### Scenario: New client, no folders exist yet

- GIVEN the client "Nuevo Cliente SA" has never submitted a document
- WHEN the system saves a document classified for "Nuevo Cliente SA" with period `06-2026` and type `Factura`
- THEN the system creates the full hierarchy: `Clientes/Nuevo Cliente SA/2026/06 - Junio/Facturas/`
- AND uploads the file to the new `Facturas/` folder
- AND returns the Drive file URL

#### Scenario: Google Drive API quota exceeded

- GIVEN the Google Drive service account has exceeded its API quota
- WHEN the system attempts to create a folder or upload a file
- THEN the system catches the quota error
- AND logs the error with `status = 'drive_quota_exceeded'`
- AND replies to the sender: "⚠️ Error al guardar tu documento. El equipo ya fue notificado. ¡Gracias!"
- AND does NOT crash

#### Scenario: Service account lacks permissions on the root folder

- GIVEN the service account email was NOT shared on the `GOOGLE_DRIVE_FOLDER_ID` folder
- WHEN the system attempts to create a subfolder
- THEN Google Drive returns a permissions error
- AND the system logs the error clearly indicating the missing permission
- AND replies to the sender with the generic error message

#### Scenario: Document type not recognized (not in expected enum)

- GIVEN Grok returns `tipo_documento: "Nota de Crédito"` (valid business document, but not in the expected enum)
- WHEN the system constructs the Drive path
- THEN the document is stored under `Clientes/{cliente}/{año}/{MM - Mes}/Otros/`
- AND `tipo_documento` is logged as-is in the database for future schema refinement

---

### REQ-CONFIRM-005: Send WhatsApp confirmation to sender

After processing (success or handled failure), the system MUST reply to the sender via Twilio WhatsApp with a confirmation message.

The confirmation message MUST include:
- A greeting with the detected client name (or a generic greeting if classification confidence is low)
- The detected document type and period (if classification succeeded)
- A clear statement that the document is saved

The system MUST use the `TWILIO_WHATSAPP_NUMBER` as the sender (`From`) and the original sender's phone number as the recipient (`To`).

#### Scenario: Successful classification and storage

- GIVEN a document was successfully classified and saved to Drive
- WHEN the system sends the confirmation
- THEN the message reads: "✅ ¡Hola {cliente}! Recibimos tu {tipo_documento} del período {periodo}. Queda registrado en tu carpeta."
- AND the message is sent via Twilio's WhatsApp API to the original sender's number

#### Scenario: Document saved but classification failed (low confidence)

- GIVEN a document was saved to `Clientes/_REVISION/` due to low classification confidence
- WHEN the system sends the confirmation
- THEN the message reads: "📸 Recibí tu documento pero no pude clasificarlo con seguridad. Facundo lo va a revisar. ¡Gracias!"

#### Scenario: Twilio message send failure

- GIVEN the Twilio API returns an error when sending the confirmation
- WHEN the send fails
- THEN the system logs the error with `status = 'confirmation_failed'`
- AND the processing record in the database still reflects the successful storage
- AND the system does NOT retry (avoids spam)
- AND the error is surfaced in the health check endpoint for monitoring

---

### REQ-DB-006: Track processing metadata in SQLite

The system MUST log every document processing attempt in a local SQLite database.

Each record MUST include:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `sender_phone` | TEXT | Sender's WhatsApp number (e.g., `+5492664123456`) |
| `filename` | TEXT | Original filename or generated name from Twilio |
| `media_content_type` | TEXT | MIME type of the received media |
| `classification_json` | TEXT | Raw JSON from Grok, or NULL if classification was skipped/failed |
| `client_name` | TEXT | Extracted client name, or NULL |
| `document_type` | TEXT | Extracted document type, or NULL |
| `period` | TEXT | Extracted period (MM-YYYY), or NULL |
| `confidence` | REAL | Classification confidence (0.0-1.0), or NULL |
| `drive_file_id` | TEXT | Google Drive file ID after successful upload, or NULL |
| `drive_folder_path` | TEXT | Full Drive path where the file was saved, or NULL |
| `status` | TEXT | Processing status: one of `received`, `classifying`, `classified`, `stored`, `confirmation_sent`, `low_confidence`, `classification_failed`, `download_failed`, `drive_error`, `ignored_no_media`, `ignored_unsupported_type` |
| `error_message` | TEXT | Error details if `status` indicates failure, or NULL |
| `created_at` | TEXT | ISO 8601 timestamp of when the record was created |
| `updated_at` | TEXT | ISO 8601 timestamp of last update |

The system SHALL update the record's `status` as processing progresses through the pipeline.

#### Scenario: Full successful processing lifecycle

- GIVEN a webhook is received for a new document
- WHEN the system processes it through all stages
- THEN the database contains one record progressing through statuses: `received` → `classifying` → `classified` → `stored` → `confirmation_sent`
- AND all fields are populated at the end (`drive_file_id`, `drive_folder_path`, etc.)
- AND `created_at` and `updated_at` timestamps reflect actual wall-clock times

#### Scenario: Processing fails at classification stage

- GIVEN the Grok API call fails
- WHEN the pipeline reaches the classification step
- THEN the record's `status` is set to `classification_failed`
- AND `error_message` contains the exception details
- AND `classification_json`, `client_name`, `document_type`, `period`, and `confidence` remain NULL
- AND the file is still saved to `Clientes/_PENDIENTE/` with a `drive_file_id` populated

---

### REQ-HEALTH-007: Expose health check and processing status

The system MUST expose a `GET /health` endpoint that returns the service status.

The health endpoint MUST return:
- `status`: `"ok"` or `"degraded"`
- `uptime_seconds`: seconds since the service started
- `checks`: an object with sub-checks for each dependency

Sub-checks MUST include:
- `twilio`: connectivity status to Twilio API
- `grok`: connectivity status to Grok API
- `drive`: connectivity status to Google Drive API
- `database`: SQLite accessibility

The system SHALL also expose `GET /stats` with aggregate counts from the processing log:
- Total documents received
- Successfully processed (status `confirmation_sent`)
- Pending review (status `low_confidence` or saved to `_REVISION`/`_PENDIENTE`)
- Failed (status `classification_failed` or `drive_error`)
- Ignored (status `ignored_*`)

#### Scenario: All dependencies healthy

- GIVEN the service is running and all external APIs are accessible
- WHEN `GET /health` is called
- THEN the response is HTTP 200 with `status: "ok"` and all checks passing

#### Scenario: Grok API is unreachable

- GIVEN the Grok API is down or the API key is invalid
- WHEN `GET /health` is called
- THEN the response is HTTP 200 with `status: "degraded"` and `checks.grok: "unreachable"`
- AND the service continues to accept webhooks (files are saved to `_PENDIENTE/`)

#### Scenario: Stats endpoint with processed documents

- GIVEN the database has 15 `confirmation_sent`, 3 `low_confidence`, 1 `classification_failed`, and 2 `ignored_no_media` records
- WHEN `GET /stats` is called
- THEN the response includes `total: 21`, `successful: 15`, `pending_review: 3`, `failed: 1`, `ignored: 2`

---

### REQ-CONFIG-008: Load configuration from environment

The system MUST read all configuration from environment variables (or a `.env` file via `python-dotenv`).

Required variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio authentication token |
| `TWILIO_WHATSAPP_NUMBER` | Yes | Twilio Sandbox WhatsApp number (e.g., `+14155238886`) |
| `XAI_API_KEY` | Yes | Grok API key from console.x.ai |
| `GOOGLE_DRIVE_CREDENTIALS` | Yes | Path to service account JSON key file |
| `GOOGLE_DRIVE_FOLDER_ID` | Yes | ID of the root Drive folder for client documents |
| `DATABASE_PATH` | No | Path to SQLite database file (default: `processing.db`) |
| `HOST` | No | Server bind address (default: `0.0.0.0`) |
| `PORT` | No | Server port (default: `8000`) |

The system MUST fail fast at startup if any required variable is missing or if the `GOOGLE_DRIVE_CREDENTIALS` file does not exist.

#### Scenario: All required variables present

- GIVEN a `.env` file with all required variables set
- WHEN the service starts
- THEN `config.py` loads and validates all variables
- AND the service starts successfully

#### Scenario: Missing required variable

- GIVEN `XAI_API_KEY` is not set in `.env` nor the environment
- WHEN the service starts
- THEN the startup fails with a clear error message: "Missing required environment variable: XAI_API_KEY"
- AND the process exits with code 1

#### Scenario: Google credentials file not found

- GIVEN `GOOGLE_DRIVE_CREDENTIALS` points to `/etc/secrets/sa.json` which does not exist
- WHEN the service starts
- THEN the startup fails with a clear error message: "Google Drive credentials file not found at: /etc/secrets/sa.json"
- AND the process exits with code 1

---

### REQ-DEPLOY-009: Dockerized deployment

The system MUST be deployable via `docker compose up` with no manual steps beyond setting environment variables.

The Dockerfile MUST:
- Use `python:3.12-slim` as the base image
- Install dependencies from `requirements.txt`
- Run the FastAPI app with uvicorn on port 8000

The docker-compose.yml MUST:
- Mount the Google credentials file as a read-only volume
- Load environment from `.env`
- Restart on failure (`restart: unless-stopped`)
- Expose port 8000

#### Scenario: First-time deployment

- GIVEN a `.env` file with valid credentials and a `service-account-key.json` in the project root
- WHEN the operator runs `docker compose up`
- THEN the container builds and starts
- AND the health endpoint returns `status: "ok"` within 10 seconds
- AND the webhook endpoint is reachable on port 8000

#### Scenario: Service restart after crash

- GIVEN the container is running
- WHEN the FastAPI process crashes (e.g., unhandled exception)
- THEN Docker restarts the container automatically
- AND the SQLite database survives the restart
- AND processing resumes for new incoming webhooks

## Edge Cases and Constraints

### EC-001: Duplicate document detection

The system SHOULD detect when the same sender sends the same file twice (same media URL or same Twilio Message SID). If a duplicate is detected, the system SHALL reply with: "📎 Ya recibimos este documento. Si necesitás enviar uno nuevo, adelante." and SHALL NOT create a duplicate file in Drive.

### EC-002: Large file handling

The system MUST enforce a maximum file size of 15 MB for downloaded media. Files exceeding this limit SHALL be rejected with a reply: "📁 El archivo es muy grande (más de 15 MB). ¿Podés comprimirlo o enviarlo en partes más chicas?"

### EC-003: Month name mapping

The system MUST map month numbers to Spanish names using a static lookup table:

```
01 → Enero, 02 → Febrero, 03 → Marzo, 04 → Abril,
05 → Mayo, 06 → Junio, 07 → Julio, 08 → Agosto,
09 → Septiembre, 10 → Octubre, 11 → Noviembre, 12 → Diciembre
```

### EC-004: Phone number normalization

Sender phone numbers from Twilio arrive in E.164 format (`whatsapp:+5492664123456`). The system MUST strip the `whatsapp:` prefix for storage and display.

### EC-005: Ngrok URL changes

When using ngrok free tier, the public URL changes every time ngrok restarts. The operator MUST update the Twilio Sandbox webhook URL in the Twilio Console after each ngrok restart. The system itself does NOT handle this automatically — this is documented as an operational procedure.

### EC-006: No persistent file storage

The system MUST NOT store downloaded files on disk permanently. Files SHALL be held in memory only during the download→classify→upload pipeline, then discarded. The authoritative copy lives in Google Drive.

### EC-007: Spanish-language responses

All user-facing messages (WhatsApp confirmations, error replies, usage instructions) MUST be in Spanish (Argentine variant where appropriate).

### EC-008: Idempotent folder creation

The Drive folder creation logic MUST be idempotent. If a folder already exists (checked by name within its parent), the system SHALL reuse the existing folder ID rather than creating a duplicate.
