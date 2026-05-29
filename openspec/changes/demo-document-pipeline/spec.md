Spec written and verified. Here's the summary:

---

## Phase Result: SDD Spec

**Status:** `completed`

**Artifact:** `openspec/changes/demo-document-pipeline/specs/pipeline/spec.md`

**Executive Summary:**

Wrote a complete domain spec for the `pipeline` domain with 9 requirements and 24 testable scenarios:

| REQ | What | Scenarios |
|-----|------|-----------|
| `REQ-WEBHOOK-001` | Receive Twilio webhook, validate media presence, handle text-only messages, malformed payloads | 4 |
| `REQ-MEDIA-002` | Download media from Twilio, handle expired URLs, unsupported types | 3 |
| `REQ-CLASSIFY-003` | Classify with Grok (xAI), structured JSON, handle low confidence, timeout, non-JSON, auth failure | 5 |
| `REQ-DRIVE-004` | Store in Google Drive with `Clientes/{name}/{year}/{MM - Mes}/{type}/` hierarchy, idempotent folders, handle quota/permission errors | 5 |
| `REQ-CONFIRM-005` | WhatsApp confirmation reply with classification summary, handle send failures | 3 |
| `REQ-DB-006` | SQLite processing log with full lifecycle tracking (14 columns, 11 status values) | 2 |
| `REQ-HEALTH-007` | `/health` and `/stats` endpoints with dependency checks | 3 |
| `REQ-CONFIG-008` | `.env` loading, fail-fast on missing vars, credential file validation | 3 |
| `REQ-DEPLOY-009` | Docker Compose deployment, auto-restart, volume mounts | 2 |

Plus 8 edge case constraints: duplicate detection, file size limits, Spanish month names, phone normalization, ngrok URL changes, memory-only file handling, Spanish responses, idempotent folders.

**Next recommended:** `sdd-design` — define module interfaces, data flow, and error handling strategy.

**Risks:** None blocking. Spec is self-contained for the WhatsApp-only demo scope. Folder structure convention should be confirmed with Facundo before going to production.