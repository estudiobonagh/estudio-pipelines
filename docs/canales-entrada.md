# Estrategia multicanal

## Como manejar las 7 entradas de datos de Facundo

---

## Los canales que menciono

| # | Canal | Quien lo inicia | Tipo de archivo | Volumen |
|---|-------|-----------------|-----------------|---------|
| 1 | WhatsApp | Cliente | Fotos, PDFs, capturas | Alto |
| 2 | Correo electronico | Cliente / Entidades | PDFs adjuntos, Excel | Alto |
| 3 | PDFs descargables de entidades | Facundo (el estudio) | PDFs de bancos, ARCA, DPIP | Medio |
| 4 | Fotografias | Cliente | Fotos de comprobantes | Alto |
| 5 | Excel | Cliente | Planillas con datos | Medio |
| 6 | Documentacion escaneada | Facundo (el estudio) | PDFs de digitalizacion | Bajo |
| 7 | Canales informales | Varios | Varios | Bajo |

---

## La estrategia: Un unico embudo de entrada

No importa por donde entre el documento. Una vez que entra al sistema, el flujo es el mismo:

```
[Canal de entrada]
       |
       v
[INA] ---> [Clasificador] ---> [Google Drive] ---> [Notificacion]
       |         |
       |    (ollama decide:
       |     - Que cliente es
       |     - Que tipo de doc
       |     - Que periodo)
       v
[No clasificado]
(va a carpeta de revision manual)
```

---

## Solucion por canal

### Canal 1: WhatsApp (ya lo tenemos cubierto)

Cliente manda foto/PDF al numero dedicado.

**Flujo:**
1. Cliente envia archivo por WhatsApp
2. Webhook de WhatsApp Cloud API lo recibe
3. FastAPI descarga, clasifica con ollama, guarda en Drive
4. Responde al cliente con confirmacion


### Canal 2: Correo electronico

Cliente o entidad envia PDF/Excel adjunto a una direccion dedicada.

**Flujo:**
1. Cliente envia email a un mail proporcionado por el estudio (o un alias tipo `facturas+clienteX@estudio.com`)
2. FastAPI recibe el email via:
   - **IMAP polling** (cada N minutos revisa la bandeja)
   - **Webhook de Gmail** (Google Workspace permite reenviar emails como webhook)
   - **Mailgun / SendGrid inbound** (servicio externo que convierte email en webhook HTTP)
3. Descarga el adjunto
4. Pasa por el mismo clasificador Gemini
5. Guarda en Drive
6. Responde al remitente: "Recibido"


### Canal 3: PDFs descargables de entidades (bancos, ARCA, DPIP)

Facundo o su equipo descargan manualmente de portales web.

**Flujo:**
1. Facundo descarga el PDF del banco / ARCA / DPIP
2. Lo arrastra a una carpeta de Google Drive llamada `INBOX/ o ENTRADAS/`
3. Un script de Python monitorea la carpeta (Google Drive API con watch)
4. Cuando aparece un archivo nuevo, lo clasifica automaticamente
5. Lo mueve a la carpeta del cliente correspondiente

**Alternativa mas simple:** Facundo reenvia el PDF por WhatsApp al bot. Un solo canal. NO ME GUSTA A MI.

### Canal 4: Fotografias

Mismo flujo que WhatsApp (Canal 1) — el cliente saca una foto y la manda.

CUBIERTO por el flujo de WhatsApp o tambien puede ser cargado por el canal 3

### Canal 5: Excel

Mismo flujo que WhatsApp o Email — el cliente manda el Excel.

CUBIERTO (WhatsApp y Email ya manejan archivos)

### Canal 6: Documentacion escaneada

Facundo escanea documentos fisicos en el estudio.

**Flujo:** Mismo que Canal 3. Lo escanea, lo deja en la carpeta `INBOX/  o ENTRADAS/` de Drive, el sistema lo procesa.


### Canal 7: Canales informales

Entrada no estructurada. El sistema no puede cubrir todo.

**Estrategia:** Educar a Facundo y su equipo para que deriven todo a los canales formales (WhatsApp, email, carpeta INBOX).

**Estado:** REQUIERE CAMBIO DE HABITO

---

## Prioridad de implementacion

| Prioridad | Canal | Por que |
|-----------|-------|---------|
| 1 | WhatsApp | Es el canal que mas volumen tiene y mas desorden genera |
| 2 | Email | Segundo canal en volumen, facil de integrar |
| 3 | Carpeta INBOX en Drive | Para PDFs descargados y escaneados. Simple de implementar. |
| 4 | Canales informales | Se resuelve con cambio de habito, no con tecnologia. |

---

## Lo que NO vamos a hacer (por ahora)

- Automatizar la descarga de portales de bancos (riesgo de seguridad, credenciales)
- Automatizar la descarga de ARCA (mismo riesgo)

---

## La meta final

Sin importar por donde entre:
- El documento se clasifica solo
- Termina en la carpeta correcta de Drive
- El cliente recibe una confirmacion
- Facundo no tiene que tocar nada

Y puede revisar desde Google Drive, que ya es su herramienta actual. Sin sistemas nuevos que aprender.
