# Asistente Documental — Demo para Estudio Bona

## ¿Qué es esto?

Un asistente automático que **recibe, clasifica y archiva** los documentos
de tus clientes. Sin que nadie tenga que descargar, renombrar ni mover
archivos a mano.

---

## El problema que resuelve

Hoy los documentos de los clientes llegan por todos lados:

- WhatsApp (fotos, PDFs)
- Correo electrónico (adjuntos)
- Descargas de bancos, ARCA, portales
- Escaneos en el estudio

Y alguien del equipo tiene que:

1. Descargar cada archivo
2. Mirarlo para saber de qué cliente es
3. Renombrarlo
4. Crear la carpeta que corresponde
5. Moverlo ahí

**Con 180 clientes, esto son horas por semana.**

---

## Cómo funciona (en simple)

El asistente hace el trabajo de recepción y archivo automáticamente:

```
📱 El cliente manda una foto por WhatsApp
       ↓
🤖 El sistema la recibe, la analiza y detecta:
   - Qué cliente es (María López)
   - Qué tipo de documento (Factura)
   - De qué mes es (Mayo 2026)
       ↓
📁 La archiva en Google Drive:
   Clientes / María López / 2026 / 05 - Mayo / Facturas / archivo.pdf
       ↓
✅ El cliente recibe un mensaje:
   "Hola María, recibimos tu Factura de mayo 2026. Queda registrada."
```

Todo esto pasa en **menos de 10 segundos**, sin que nadie del estudio
toque nada.

---

## Por dónde entran los documentos

El asistente puede recibir documentos por tres vías distintas.

Esto es importante porque **no importa por dónde llegue el documento**:
una vez que entra al sistema, el proceso es siempre el mismo.

- **WhatsApp**: el cliente manda la foto o PDF a un número dedicado del
  estudio. El sistema la recibe automáticamente.

- **Correo electrónico**: el cliente o una entidad manda un adjunto a
  un buzón del estudio. El sistema revisa el correo periódicamente y
  procesa lo que encuentra.

- **Carpeta en Drive**: Facundo o su equipo descargan un PDF de un
  banco y lo sueltan en una carpeta llamada "Bandeja de entrada" en
  Google Drive. El sistema lo detecta y lo procesa solo.

---

## Dónde quedan los archivos

En Google Drive, dentro de la cuenta que ya usa el estudio. La estructura
es la misma que usan hoy:

```
Clientes/
  María López/
    2026/
      05 - Mayo/
        Facturas/
        Recibos/
        Comprobantes/
        Bancos/
  Municipalidad X/
    2026/
      05 - Mayo/
        Facturas/
        ...
```

Si el sistema no puede clasificar un documento con seguridad, lo deja en
una carpeta especial para que alguien del estudio lo revise:

- **Clientes/_REVISION/**: documentos que el sistema no pudo clasificar
  con suficiente certeza.

- **Clientes/_PENDIENTE/**: documentos donde hubo un error técnico y
  necesitan atención.

---

## Lo que el sistema NO hace

Para que quede claro desde el principio, esto es una **demo demostrativa**.
No reemplaza el trabajo del estudio, lo complementa en una tarea
específica: la recepción y archivo de documentos.

El sistema **no**:

- Prepara declaraciones juradas
- Calcula impuestos
- Se conecta a ARCA ni a bancos
- Reemplaza el criterio del contador
- Tiene panel de control ni dashboard (por ahora)

**Sí** hace:

- Recibe documentos por WhatsApp, email y Drive
- Los clasifica automáticamente
- Los archiva en la carpeta correcta
- Confirma al cliente que los recibió
- Lleva un registro de todo lo procesado

---

## ¿Qué sigue después de la demo?

La demo está pensada para **probar el concepto** con 2 o 3 clientes
reales. Si funciona bien, el plan es:

1. **Fase 1**: Recepción unificada de documentos (esto es lo que hace
   la demo). Sacar la carga de recibir y archivar.

2. **Fase 2**: Alertas de documentación faltante, recordatorios de
   vencimientos, detección de duplicados.

3. **Fase 3**: Panel de control donde Facundo pueda ver de un vistazo
   el estado documental de cada cliente, qué falta, qué venció.

---

## Seguridad y privacidad

- **Los documentos nunca salen del control del estudio.** Se procesan
  en un servidor propio y se guardan en el Google Drive del estudio.

- **La inteligencia artificial no almacena ni aprende de los
  documentos.** Solo los analiza en el momento y descarta cualquier
  copia.

- **No se accede a claves fiscales ni cuentas bancarias.** El sistema
  no necesita ni debe tener acceso a información sensible de ARCA o
  de los bancos.

- **Todo el tráfico es cifrado** (HTTPS).

---

## Preguntas frecuentes

**¿El cliente tiene que instalar algo?**
No. Sigue usando WhatsApp como siempre. Solo manda el documento a un
número dedicado en lugar de al WhatsApp personal.

**¿Qué pasa si el sistema se equivoca al clasificar?**
El documento queda en la carpeta `_REVISION/` para que alguien del
estudio lo revise y lo mueva manualmente. El sistema aprende de estos
casos con el tiempo.

**¿Funciona con cualquier tipo de documento?**
Funciona con fotos (JPG, PNG), PDFs, y archivos Excel. Si un cliente
manda algo que no entra en esas categorías, el sistema avisa.

**¿Cuánto cuesta?**
La demo no tiene costo operativo. Para la versión final, el costo
estimado es de $15-20 USD por mes (servidor + APIs), sin límites de
uso. Mucho menos que las horas que hoy se invierten en archivar.

---

*Demo demostrativa — Mayo 2026*
*Estudio Bona & Asoc. — San Luis, Argentina*
