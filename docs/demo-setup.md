# Demo rapido: Arquitectura simplificada y API keys

## Sin WhatsApp Business API. Con Twilio Sandbox.

---

## Por que Twilio Sandbox para la demo

La idea de la demo es validar el flujo completo sin tener que pasar por el proceso de verificacion de negocio de Meta (que puede tomar dias o semanas).

| Opcion | Tiempo de setup | Costo | Limitacion |
|--------|----------------|-------|------------|
| **Twilio Sandbox** | 15 minutos | Gratis (~$0.005 por msg despues) | Solo numeros que acepten el codigo de invitacion |
| Meta WhatsApp Cloud API | Dias/semanas (verificacion) | Gratis primeras 1k conversaciones | Requiere pagina web, dominio verificado |
| whatsapp-web.js (no oficial) | 10 minutos | Gratis | Riesgo de baneo. Inestable. No para produccion. |

**Twilio Sandbox** es el camino mas rapido para la demo:
- Te dan un numero temporal
- Los numeros que participan tienen que enviar un codigo magico para unirse al sandbox
- Una vez unidos, pueden enviar y recibir mensajes
- API simple con HTTP POST

**Limitacion del sandbox:** Solo los numeros que envien el codigo de activacion pueden participar. Para la demo con Facundo y 2 o 3 clientes de prueba alcanza perfecto.

---

## Arquitectura de la demo

```
Cliente (numero unido al sandbox)
  |
  | Envia foto/PDF por WhatsApp al numero Twilio Sandbox
  v
Twilio WhatsApp Sandbox
  |
  | Twilio envia un webhook HTTP POST a tu servidor
  v
FastAPI (localhost / ngrok / VPS)
  |
  | 1. Recibe el media URL de Twilio
  | 2. Descarga el archivo desde Twilio
  | 3. Envia a Gemini para clasificar
  | 4. Guarda en Google Drive
  | 5. Responde al cliente por Twilio
  v
Google Drive de Facundo
```

---

## API keys necesarias

### 1. Twilio

| Key | Donde se obtiene | Para que |
|-----|-----------------|----------|
| `TWILIO_ACCOUNT_SID` | Consola de Twilio (twilio.com/console) | Identificar tu cuenta |
| `TWILIO_AUTH_TOKEN` | Consola de Twilio | Autenticar requests |
| `TWILIO_WHATSAPP_NUMBER` | Sandbox de Twilio (WhatsApp > Sandbox) | Numero que recibe los mensajes |

**Tiempo de obtencion:** 10 minutos (crear cuenta + activar sandbox)

### 2. Grok (xAI)

| Key | Donde se obtiene | Para que |
|-----|-----------------|----------|
| `XAI_API_KEY` | console.x.ai | Clasificar documentos con IA (imagenes, PDFs, Excel) |

**Tiempo de obtencion:** 5 minutos (crear cuenta + API key)

**Capacidades de Grok para la demo:**
- Vision para analisis de imagenes y fotografias ✅
- Lectura de PDFs como imagenes (cada pagina se envia como imagen) ✅
- Archivos Excel y texto plano ✅
- Clasificacion de documentos por contenido ✅

### 3. Google Drive (Service Account)

| Key | Donde se obtiene | Para que |
|-----|-----------------|----------|
| `GOOGLE_DRIVE_CREDENTIALS` | Google Cloud Console > IAM > Service Accounts | Guardar archivos en Drive |
| `GOOGLE_DRIVE_FOLDER_ID` | La URL de la carpeta en Drive | ID de la carpeta raiz donde se guarda todo |

**Tiempo de obtencion:** 15 minutos (crear proyecto en GCP, habilitar Drive API, crear service account, compartir carpeta)

### 4. Ngrok (para desarrollo local)

| Key | Donde se obtiene | Para que |
|-----|-----------------|----------|
| `NGROK_AUTH_TOKEN` | ngrok.com (gratis) | Exponer tu servidor local a internet para que Twilio pueda enviar los webhooks |

**Alternativa a ngrok:** Si deployas directo a Railway / Fly.io, no necesitas ngrok porque ya tienen URL publica.

---

## Setup rapido paso a paso

```
1. Crear cuenta en Twilio (twilio.com) -> Activar WhatsApp Sandbox
2. Crear API key en Google AI Studio
3. Crear service account en Google Cloud Console
4. Compartir carpeta de Google Drive con el email del service account
5. Crear archivo .env con todas las keys
6. Correr ngrok para exponer el servidor local
7. Configurar el webhook de Twilio a la URL de ngrok
8. Enviar un documento de prueba desde WhatsApp
```

---

## Variables de entorno (.env)

```env
# Twilio
TWILIO_ACCOUNT_SID=tu_account_sid
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_WHATSAPP_NUMBER=+14155238886  # numero del sandbox

# Grok (xAI)
XAI_API_KEY=tu_xai_api_key

# Google Drive
GOOGLE_DRIVE_CREDENTIALS=path/to/service-account-key.json
GOOGLE_DRIVE_FOLDER_ID=id_de_la_carpeta_en_drive

# Servidor
HOST=0.0.0.0
PORT=8000
```

---

## Dependencias actualizadas (requirements.txt)

```
fastapi
uvicorn
httpx
openai
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
python-multipart
pydantic
python-dotenv
sqlalchemy
aiosqlite
twilio
openpyxl
email-validator
```

**Nueva:** `twilio` (reemplaza la integracion directa con WhatsApp Cloud API)
**Cambio:** `openai` en lugar de `google-generativeai` (Grok usa API compatible con OpenAI)

---

## Costo de la demo

| Recurso | Costo |
|---------|-------|
| Twilio Sandbox | $0 (gratis para pruebas) |
| Grok API | ~$0 (free tier disponible en console.x.ai) |
| Google Drive | $0 (ya lo tiene Facundo) |
| Ngrok | $0 (free tier) |
| **Total demo** | **$0** |
