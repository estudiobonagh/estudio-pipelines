# SDD Proposal: Demo Document Pipeline

**Change ID:** `demo-document-pipeline`
**Status:** draft
**Author:** Gentle AI (SDD executor)
**Date:** 2026-05-29

---

## Intent

Build a working demo of the document reception and classification pipeline for Facundo Bona's accounting firm. The demo proves the core flow end-to-end: a client sends a document via WhatsApp → the system receives, classifies, and files it into Google Drive automatically — zero manual intervention.

This is **Etapa 1, Fase 1A** from the agreed plan with Facundo: "Recepción unificada."

## Scope

### In scope

| Component | What it does | Technology |
|-----------|-------------|------------|
| WhatsApp webhook | Receives messages (images, PDFs, Excel) from Twilio Sandbox | FastAPI + Twilio SDK |
| File download | Downloads media from Twilio's temporary URLs | httpx |
| AI classification | Analyzes the document, returns structured JSON (client, document type, period, amount, confidence) | Grok API (xAI, OpenAI-compatible) |
| Google Drive storage | Creates folder hierarchy `Clientes/[Name]/[Year]/[Month]/[Type]/` and saves the file | Google Drive API (service account) |
| WhatsApp confirmation | Replies to the client confirming receipt and classification | Twilio SDK |
| Metadata tracking | Logs every processed document (sender, classification, timestamp, Drive URL) | SQLite |
| Docker deployment | Containerized app runnable on any VPS | Docker + Docker Compose |

### Out of scope (explicitly deferred)

| Item | Why deferred |
|------|-------------|
| Email channel (Mailgun) | Demo uses WhatsApp only — email adds complexity without changing the pipeline |
| Drive INBOX watcher | Manual folder drop via Drive watch is a Phase 1B optimization |
| Multi-channel processor abstraction | Premature for demo — single channel validates the concept |
| ARCA / DPIP integration | Etapa 2 — requires tax authority web services, security review |
| Dashboard or web UI | Etapa 2 — Facundo explicitly requested "no new systems to learn" |
| Client onboarding / registration | Hardcoded client list for demo; real onboarding comes later |
| Vencimientos / alerts | Phase 1B — requires calendar logic and client list |
| Production WhatsApp (Meta Cloud API) | Twilio Sandbox is sufficient for demo with 2-3 test clients |
| Auth / login / multi-user | Single-user demo; authentication is a production concern |
| Performance / scaling | Single-instance FastAPI; handles demo volume (~50 docs/day) |

## Success Criteria

The demo is successful when all of the following are true:

1. **End-to-end flow works**: A WhatsApp user (joined to the Twilio Sandbox) sends a photo/PDF, and within 10 seconds the file appears classified in the correct Google Drive folder.

2. **Classification accuracy**: Grok correctly identifies the client name, document type (Factura, Recibo, Comprobante, Extracto), and period (MM-YYYY) with >80% confidence on a sample of 10 test documents provided by Facundo.

3. **Folder structure matches existing convention**: Files land in `Clientes/[Nombre]/[Año]/[MM - Mes]/[Tipo]/archivo.ext`, matching the structure Facundo already uses.

4. **Confirmation reply**: The sender receives a WhatsApp message confirming receipt with the classification summary (e.g., "Hola María, recibimos tu Factura del período 05-2026. Queda registrada.").

5. **Runs locally or on a VPS**: `docker compose up` brings the entire system online. Ngrok exposes the webhook endpoint to Twilio.

6. **Zero cost to run**: Twilio Sandbox ($0), Grok free tier ($0), Google Drive (existing), Ngrok free tier ($0).

## Affected Areas

### New files (project root)

```
main.py                 # FastAPI app — webhook endpoint, health check
classifier.py           # Grok API integration — sends file, parses JSON response
drive_service.py        # Google Drive API — create folder, upload file, build path
whatsapp_service.py     # Twilio integration — download media, send confirmation
processor.py            # Pipeline orchestrator — ties classifier + drive + whatsapp
models.py               # Pydantic models for classification results and processing records
config.py               # Environment variable loading and validation (.env)
database.py             # SQLite schema and operations for processing log
requirements.txt        # Python dependencies
Dockerfile              # Container build
docker-compose.yml      # Local dev / VPS deployment
.env.example            # Template for required environment variables
```

### Existing files

| File | Action |
|------|--------|
| `docs/` | Reference only — no changes needed during implementation |
| `openspec/config.yaml` | Already created during SDD init |
| `.gitignore` | May need additions for `.env`, `__pycache__`, `*.db` |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Twilio Sandbox webhook latency/reliability | Low | Medium | Test with direct curl; ngrok free tier resets every 2h — note this in docs |
| Grok API classification quality on Argentine documents | Medium | High | Test with Facundo's real documents early; have fallback prompt tuning strategy |
| Google Drive API rate limits or quota | Low | Low | Service account has generous free tier (1M requests/day); single-user demo won't hit limits |
| Folder structure mismatch with Facundo's conventions | Medium | Medium | Confirm exact path schema with Facundo before finalizing; keep path builder configurable via `config.py` |
| Twilio Sandbox requires sender opt-in (join code) | High (for testers) | Medium | Document the join process clearly; provide WhatsApp-ready instructions for test clients |
| Dependency conflicts (google-api-python-client + fastapi + twilio) | Low | Low | Pin versions in `requirements.txt`; Docker ensures reproducible environment |

## Rollback

The demo is a standalone service with no effect on existing systems:

- **Code rollback**: Delete the project directory. No persistent state outside of it.
- **Google Drive rollback**: Delete the `Clientes/` folder created during testing. No existing files are touched.
- **Twilio rollback**: The Sandbox number expires or can be deactivated from Twilio Console.
- **Data rollback**: SQLite database is local to the project. Delete `processing.db` to reset.

No production data, credentials, or client-sensitive information is at risk. The demo operates entirely with test data.

## Implementation Plan (forecast)

| Phase | Effort | Description |
|-------|--------|-------------|
| Spec | 30 min | Formalize requirements and acceptance scenarios |
| Design | 30 min | Module interfaces, data flow, error handling strategy |
| Tasks | 45 min | Break into atomic, reviewable commits |
| Apply | 2-3 h | Write the code across 8-10 modules |
| Verify | 1 h | End-to-end test with Twilio Sandbox, Grok, and Drive |

**Total estimated:** 4-6 hours of focused work.

## Dependencies

| Dependency | Status | Action needed |
|-----------|--------|---------------|
| Twilio account + Sandbox | Not created | User provides or creates during apply phase |
| xAI (Grok) API key | Not created | User provides or creates at console.x.ai |
| Google Cloud service account | Not created | User creates in GCP Console, shares Drive folder |
| Ngrok auth token | Not created | User signs up at ngrok.com (free) |
| Python 3.12+ | Available (3.14.5) | ✅ |
| Docker | TBD | Check during apply phase |

## Approval

- [ ] Scope confirmed — WhatsApp-only demo, no dashboard, no ARCA
- [ ] Folder structure convention confirmed with Facundo
- [ ] API keys obtained or plan for obtaining them defined
- [ ] Test documents identified (2-3 per type: factura, recibo, comprobante)
