# Stack tecnologico recomendado v2

## Para la Fase 1A — Recepcion unificada de documentos

## Version: Python puro (descartado n8n)

---

## Filosofia

Nada de low-code. Nada de cajas negras. Python puro, liviano, control total.
Cada componente es reemplazable individualmente. Sin vendor lock-in.
Corre donde quieras (VPS, Docker, tu propia compu).

---

## Stack definitivo

| Componente | Tecnologia | Por que |
|------------|------------|---------|
| **Webhook / API** | FastAPI | Async, rapido, tipado, documentacion automatica (Swagger) |
| **WhatsApp** | WhatsApp Cloud API (Meta) via httpx | API oficial, HTTP plano, sin dependencias raras |
| **Clasificacion** | Grok API (google-generativeai) o LLM local | Clasifica imagenes y PDFs sin OCR extra |
| **Google Drive** | google-api-python-client | SDK oficial de Google, maneja archivos, carpetas, permisos |
| **Email** | Mailgun inbound webhook | Transforma emails entrantes en webhooks HTTP |
| **Drive Watch** | Google Drive API push notifications | Detecta archivos nuevos en la carpeta Bandeja |
| **Cola de tareas** | Celery + Redis (solo si escala) | Para procesos pesados sin bloquear el webhook |
| **Almacenamiento local** | SQLite / PostgreSQL | Solo metadata de tracking (quien envio, cuando, que se clasifico) |
| **Contenedor** | Docker + Docker Compose | Para deployar limpio en cualquier VPS |
| **Servidor** | VPS basico ($10/mes) | DigitalOcean, Railway, Fly.io, Scaleway |

---

## Arquitectura (7 canales de entrada unificados)

Facundo recibe documentos por 7 canales distintos. Todos convergen en el mismo pipeline de procesamiento.

```
                          +-------------------+
                          |  BANDEJA DE       |
                          |  ENTRADA          |
                          |  (Google Drive)   |
                          |                   |
  +----------+            |  Archivos sueltos |
  | WhatsApp |----------->|  que alguien      |
  | Business |            |  descargo de un   |
  | (numero  |            |  banco/ARCA/etc   |
  |  doc)    |            |                   |
  +----------+            +--------+----------+
                                   |
  +----------+                     |
  |  Email   |---------------------+
  |  doc     |  Adjuntos por email
  |@estudio  |
  +----------+                     |
                                   |
  +----------+                     |
  |  Drive   |---------------------+
  |  Bandeja |  Archivos tirados ahi
  |  (catch  |  manualmente
  |  all)    |
  +----------+
                                   |
                            v
                   +------------------+
                   |   FastAPI         |
                   |   (processor.py)  |
                   |                  |
                   |  1. Gemini       |
                   |  2. Clasifica    |
                   |  3. Renombra     |
                   |  4. Mueve a      |
                   |     carpeta      |
                   |     correcta     |
                   +------------------+
                            |
                            v
                   +------------------+
                   |  Google Drive    |
                   |  Estructurado    |
                   |                  |
                   |  /Clientes/      |
                   |    /[Nombre]/    |
                   |      /2026/      |
                   |       /05/       |
                   |  Facturas/       |
                   |  Recibos/        |
                   |  Bancos/         |
                   +------------------+
```

### Cobertura por canal

| Canal | Como se recibe | Implementacion |
|-------|---------------|----------------|
| WhatsApp | Webhook WhatsApp Cloud API | whatsapp.py |
| Email | Mailgun inbound webhook | email_webhook.py |
| Descargas de bancos/ARCA | Google Drive watch (carpeta Bandeja) | drive_watcher.py |
| Fotografias | Via WhatsApp o Drive Bandeja | Absorbido por WhatsApp/Drive |
| Excel | Via email o Drive Bandeja | processor.py + pandas |
| Escaneados | Via email o WhatsApp | Absorbido por email/WhatsApp |
| Otros | Drive Bandeja (catch-all) | drive_watcher.py |

**Clave del diseno:** Da igual por donde entre el archivo — `processor.py` ejecuta el mismo pipeline de clasificacion (Gemini) y guardado (Google Drive).

---

## Estructura del proyecto Python

```
proyecto/
|
|-- main.py              # FastAPI app, webhook endpoints
|-- whatsapp.py          # Modulo para enviar/recibir de WhatsApp API
|-- email_webhook.py     # Modulo Mailgun inbound webhook para email
|-- drive_watcher.py     # Modulo que monitorea carpeta Bandeja de Drive
|-- drive.py             # Modulo para Google Drive (crear carpetas, subir, mover)
|-- classifier.py        # Modulo para clasificar documentos con Gemini
|-- processor.py         # Pipeline UNICO: recibe archivo de cualquier canal y lo procesa
|-- models.py            # Modelos de datos (pydantic)
|-- config.py            # Configuracion (variables de entorno)
|-- database.py          # SQLite o Postgres para tracking
|-- requirements.txt     # Dependencias
|-- Dockerfile           # Para deployar
|-- docker-compose.yml   # Para correr con Redis si hace falta
|
|-- tests/
    |-- test_whatsapp.py
    |-- test_email.py
    |-- test_drive.py
    |-- test_classifier.py
    |-- test_processor.py
```

### Responsabilidad de cada modulo

| Modulo | Que hace |
|--------|----------|
| `main.py` | Rutas FastAPI: webhook de WhatsApp, webhook de email, health check |
| `whatsapp.py` | Recibir mensajes de WhatsApp Cloud API, descargar archivos de media, enviar confirmaciones |
| `email_webhook.py` | Recibir adjuntos via Mailgun inbound webhook, pasarlos a processor |
| `drive_watcher.py` | Monitorear carpeta "Bandeja de entrada" en Google Drive, detectar archivos nuevos, pasarlos a processor |
| `drive.py` | Operaciones de Google Drive: crear carpeta, subir archivo, mover archivo, renombrar, buscar |
| `classifier.py` | Enviar archivo a Gemini, recibir clasificacion estructurada (cliente, tipo, periodo) |
| `processor.py` | **Pipeline unico.** Recibe un archivo + metadata del canal de origen. Llama a classifier, llama a drive. Da igual si vino de WhatsApp, email o Drive. |
| `models.py` | Pydantic models: DocumentClassification, ProcessingResult, etc. |
| `config.py` | Variables de entorno: credenciales, IDs, rutas |
| `database.py` | SQLite para tracking: quien envio, cuando, que se clasifico, donde se guardo |

---

## Dependencias (requirements.txt)

```
fastapi
uvi\orn
httpx
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
google-generativeai
python-multipart
pydantic
python-dotenv
sqlalchemy
aiosqlite
openpyxl          # para procesar archivos Excel
email-validator   # para validar emails entrantes
```

**Nada mas.** Sin frameworks pesados, sin magia. Cada libreria hace exactamente una cosa.

---

## Flujo detallado en Python

### 1. Webhook de WhatsApp (FastAPI)

```python
@app.post("/webhook")
async def webhook_receive(body: dict):
    # Verificar que sea un mensaje con archivo
    if "messages" in body["entry"][0]["changes"][0]["value"]:
        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        if "image" in message or "document" in message:
            # Encolar para procesar
            await process_document.delay(message)
            return {"status": "ok"}
```

### 2. Descargar archivo de WhatsApp

```python
async def download_media(media_id: str) -> bytes:
    # 1. Pedir URL de descarga a WhatsApp API
    # 2. Descargar el archivo
    # 3. Retornar los bytes
```

### 3. Clasificar con Gemini

```python
def classify_document(file_bytes: bytes, filename: str) -> dict:
    prompt = """
    Clasifica este documento financiero.
    Devuelve SOLO JSON:
    {
        "cliente": "nombre del cliente posible",
        "tipo_documento": "Factura | Recibo | Comprobante | Extracto | Otro",
        "periodo": "MM-YYYY",
        "proveedor": "nombre del emisor si se identifica",
        "monto": 0.00,
        "confianza": 0.0-1.0
    }
    """
    response = model.generate_content([prompt, file_bytes])
    return parse_json(response.text)
```

### 4. Guardar en Google Drive

```python
def save_to_drive(file_bytes: bytes, metadata: dict) -> str:
    # 1. Construir ruta: Clientes/[cliente]/2026/05/Facturas/
    # 2. Crear carpeta si no existe
    # 3. Subir archivo con nombre: 2026-05_Factura_Proveedor.pdf
    # 4. Retornar URL del archivo
```

### 5. Responder al cliente

```python
def send_confirmation(to: str, metadata: dict):
    message = f"Hola {metadata['cliente']}, "
    message += f"recibimos tu {metadata['tipo_documento']} "
    message += f"del periodo {metadata['periodo']}. "
    message += "Queda registrada en tu carpeta."
    # Enviar por WhatsApp API
```

---

## Despliegue

### Opcion 1: Docker en un VPS (recomendada)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    restart: always
```

### Opcion 2: Railway o Fly.io

- Subis el repo a GitHub
- Conectas con Railway / Fly.io
- Ellos manejan el deploy automatico
- Sin tener que tocar un VPS

---

## Costos finales

| Recurso | Costo |
|---------|-------|
| VPS (DigitalOcean / Railway) | ~$5-10/mes |
| WhatsApp Cloud API | ~$7/mes (180 clientes) |
| Gemini API | ~$3/mes |
| Google Drive | Ya lo tiene |
| **Total** | **~$15-20/mes** |

Sin limites de ejecucion. Sin cuellos de botella de n8n. Sin pagar por nodo.
Escala horizontalmente si hace falta (mas instancias de FastAPI).

---

## Ventajas de Python vs n8n

| Aspecto | n8n | Python |
|---------|-----|--------|
| **Costo a escala** | Se vuelve caro (nodos, executions) | Fijo ($15/mes VPS) |
| **Cuellos de botella** | Si, en alta concurrencia | Async, maneja cientos de requests por segundo |
| **Control** | Limitado a lo que los nodos permiten | Total. Haces lo que quieras. |
| **Mantenimiento** | Actualizaciones de n8n pueden romper flujos | Tu codigo, tu control |
| **Testing** | Dificil de testear automaticamente | Tests unitarios con pytest |
| **Versionado** | No hay git friendly | Git desde el dia 1 |
| **Modificaciones** | UI visual, pero limitada | Cambias el codigo y listo |

---

## Proximo paso

Arrancar el proyecto con:

```bash
mkdir proyecto-facundo
cd proyecto-facundo
python -m venv venv
pip install fastapi uvicorn httpx google-generativeai google-api-python-client python-dotenv
```

Y construir el webhook basico en ~una tarde.
