# Estudio Pipelines — Demo de Recepción Documental

Pipeline automatizado de recepción, clasificación y archivo de documentos
contables. Construido para el estudio de Facundo Bona, San Luis, Argentina.

## ¿Qué hace?

Recibe documentos por **WhatsApp**, **email** o **carpeta de Google Drive**,
los clasifica con inteligencia artificial y los archiva automáticamente en
la estructura de carpetas correcta dentro de Google Drive.

```
Cliente manda foto/PDF → Sistema clasifica → Drive: Clientes/María/2026/05 - Mayo/Facturas/
```

El contador deja de descargar, renombrar y mover archivos a mano.

## Canales de entrada

| Canal | Cómo funciona | Estado |
|-------|--------------|--------|
| **WhatsApp** | Webhook de Twilio — el cliente manda al número del estudio | ✅ |
| **Email** | IMAP polling — adjuntos enviados a un buzón dedicado | ✅ |
| **Drive INBOX** | Carpeta "Bandeja de entrada" en Drive — soltás archivos y se procesan | ✅ |

Los tres canales convergen en el mismo pipeline de procesamiento.

## Arquitectura

```
                         ┌──────────────────────┐
  WhatsApp ──────────────┤                      │
  Email ─────────────────┤   FastAPI + Celery   │
  Drive INBOX ───────────┤   (processor.py)     │
                         │                      │
                         └──────────┬───────────┘
                                    │
                          ┌─────────▼─────────┐
                          │   Grok (xAI)       │
                          │   Clasificación IA │
                          └─────────┬─────────┘
                                    │
                          ┌─────────▼─────────┐
                          │   Google Drive     │
                          │   Clientes/...     │
                          └───────────────────┘
```

### Stack

| Componente | Tecnología |
|------------|------------|
| API | FastAPI (Python 3.12+) |
| WhatsApp | Twilio Sandbox |
| Email | IMAP (aioimaplib) |
| Clasificación IA | Grok (xAI) — API compatible con OpenAI |
| Almacenamiento | Google Drive API |
| Base de datos | SQLite (async, SQLAlchemy) |
| Deploy | Docker / Railway |

## Estructura del proyecto

```
├── main.py                 # FastAPI — webhook, health, stats
├── processor.py            # Pipeline orquestador
├── classifier.py           # Clasificación con Grok (xAI)
├── drive_service.py        # Google Drive — carpetas, upload
├── whatsapp_service.py     # Twilio — WhatsApp
├── email_service.py        # IMAP — email
├── drive_watcher.py        # Drive INBOX watcher
├── config.py               # Variables de entorno
├── models.py               # Modelos Pydantic
├── database.py             # SQLite async
├── Dockerfile              # Contenedor
├── docker-compose.yml      # Deploy local
├── requirements.txt        # Dependencias
└── docs/                   # Documentación del proyecto
```

## Setup rápido

### 1. Clonar e instalar

```bash
git clone https://github.com/estudiobonagh/estudio-pipelines.git
cd estudio-pipelines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con las API keys reales
```

Variables obligatorias:

| Variable | Descripción |
|----------|-------------|
| `TWILIO_ACCOUNT_SID` | SID de cuenta Twilio |
| `TWILIO_AUTH_TOKEN` | Token de autenticación Twilio |
| `TWILIO_WHATSAPP_NUMBER` | Número del sandbox de Twilio |
| `XAI_API_KEY` | API key de Grok (console.x.ai) |
| `GOOGLE_DRIVE_CLIENTS_ID` | ID de la carpeta raíz en Drive |
| `GOOGLE_DRIVE_CREDENTIALS_JSON` | JSON de la service account de Google |

### 3. Exponer con ngrok (solo WhatsApp)

```bash
ngrok http 8000
```

Configurar la URL de ngrok como webhook en la consola de Twilio.

### 4. Ejecutar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

O con Docker:

```bash
docker compose up
```

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/webhook` | Webhook de Twilio WhatsApp |
| `GET` | `/health` | Health check con estado de dependencias |
| `GET` | `/stats` | Estadísticas de documentos procesados |
| `GET` | `/docs` | Swagger UI (documentación automática) |

## Estructura de carpetas en Drive

```
Clientes/
├── María López/
│   └── 2026/
│       └── 05 - Mayo/
│           ├── Facturas/
│           ├── Recibos/
│           ├── Comprobantes/
│           └── Bancos/
├── Municipalidad X/
│   └── ...
├── _REVISION/          ← Documentos con baja confianza de clasificación
└── _PENDIENTE/         ← Documentos que no se pudieron clasificar
```

## Flujo de procesamiento

1. **Recepción** — El documento entra por WhatsApp, email o Drive INBOX
2. **Descarga** — El sistema obtiene el archivo (bytes)
3. **Clasificación** — Grok analiza y devuelve: cliente, tipo, período, monto, confianza
4. **Archivo** — Se guarda en `Clientes/{nombre}/{año}/{mes}/{tipo}/archivo.ext`
5. **Confirmación** — WhatsApp: el cliente recibe "Recibimos tu factura de mayo 2026"
6. **Registro** — Cada paso queda registrado en la base de datos

## Licencia

Privado — Estudio Bona & Asoc.
