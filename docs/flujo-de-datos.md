# Flujo de los datos: como viaja la informacion

## Lo que pasa desde que el cliente manda un documento hasta que esta listo en el estudio

---

## Mapa del flujo completo (simple)

```
CLIENTE
  |
  | (1) Envia factura/comprobante por WhatsApp
  v
NUMERO DE WHATSAPP DEDICADO
  |
  | (2) Recibe automaticamente
  v
SISTEMA DE CLASIFICACION
  |
  | (3) Detecta:
  |    - Que cliente es
  |    - Que tipo de documento
  |    - A que periodo corresponde
  v
GOOGLE DRIVE DEL ESTUDIO
  |
  | (4) Guarda en la carpeta correcta:
  |    Clientes > [Nombre] > [Año] > [Mes] > [Tipo] > archivo.pdf
  v
CLIENTE Y ESTUDIO RECIBEN CONFIRMACION
```

---

## Paso a paso

### Paso 1: El cliente envia

El cliente manda una foto o PDF por WhatsApp al numero del estudio. Igual que hoy. Sin cambios para el.

**Lo que NO cambia para el cliente:** Sigue usando WhatsApp como siempre.

**Lo que cambia:** Envia a un numero dedicado solo para documentos, no al WhatsApp personal.

---

### Paso 2: El sistema recibe

El archivo llega automaticamente al sistema. No hay nadie descargando, renombrando, ni moviendo archivos.

---

### Paso 3: El sistema clasifica

El sistema analiza el archivo y determina tres cosas:

1. **Que cliente es:** por el numero de WhatsApp que envio
2. **Que tipo de documento:** factura, recibo, comprobante, extracto bancario
3. **A que periodo corresponde:** por la fecha del archivo o la fecha de envio

**Todo esto sucede en menos de 5 segundos.**

---

### Paso 4: Se guarda en Google Drive

El archivo se guarda automaticamente en la carpeta que le corresponde:

**Estructura de carpetas:**
```
Clientes/
  |-- Maria Lopez/
  |     |-- 2026/
  |     |     |-- 05 - Mayo/
  |     |     |     |-- Facturas/
  |     |     |     |-- Recibos/
  |     |     |     |-- Comprobantes/
  |     |     |     |-- Bancos/
  |     |     |-- 06 - Junio/
  |-- Municipalidad X/
  |     |-- 2026/
  |     |     |-- 05 - Mayo/
  |     |     |     |-- Facturas/   (420 facturas)
  |     |     |     |-- Bancos/
  |-- Cliente Z/
```

---

### Paso 5: Confirmacion

El sistema responde automaticamente al cliente:

> "Hola Maria, recibimos tu factura de mayo 2026. Queda registrada."

Y al equipo del estudio le aparece en el Drive ya clasificado y listo para usar.

---

## Donde se procesa cada cosa

```
CLIENTE
  |
  | WhatsApp ---- Los mensajes pasan por Meta (WhatsApp). Ya lo hace hoy.
  v
SISTEMA DE CLASIFICACION (servidor propio)
  |
  | Inteligencia artificial que corre en un servidor privado y gestionado por nosotros.
  | Los datos NO salen de ahi. NO se envian a OpenAI, Google, ni a nadie.
  | El servidor debe estar bajo normas de privacidad europeas (GDPR) para maxima confidencialidad.
  v
GOOGLE DRIVE DEL ESTUDIO
  |
  | Los archivos estan siempre en la cuenta de Google del estudio.
  | El sistema solo los deja ahi. No los copia, no los almacena afuera.
```

---

## Seguridad en cada paso

| Donde | Proteccion |
|-------|------------|
| **WhatsApp** | Cifrado de extremo a extremo. Ya lo usan hoy. |
| **Servidor de clasificacion** | Datos procesados localmente, nunca reenviados a terceros. Sin almacenamiento persistente. |
| **Google Drive** | Cifrado de Google. El estudio tiene control total de permisos. |
| **Comunicaciones** | Todo el trafico es HTTPS (cifrado). |

---

## Lo que NO pasa

- Los datos no se guardan en servidores de terceros
- La inteligencia artificial no aprende de tus documentos ni los reenvia
- No hay almacenamiento externo fuera de Google Drive
- No hay acceso a claves fiscales ni a cuentas bancarias

---

## mini resumen

```
ANTES:
  Cliente -> WhatsApp personal -> Contador descarga -> Renombra -> Clasifica -> Drive

DESPUES:
  Cliente -> Numero dedicado -> SISTEMA LO HACE TODO -> Drive listo
```

**Lo que Facundo gana:**
- 0 minutos persiguiendo documentos
- 0 archivos renombrados a mano
- 0 carpetas creadas manualmente
- 100% de trazabilidad
- 100% de los datos bajo su control
