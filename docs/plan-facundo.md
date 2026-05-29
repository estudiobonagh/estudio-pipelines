# Plan de accion — Facundo Bona

## Datos relevados de la charla + brief escrito

---

## El cliente

| Dato | Valor |
|------|-------|
| Nombre | Facundo Bona |
| Equipo | 4 empleados + su padre + el = 6 personas |
| Clientes | 180 |
| Mix de clientes | Monotributistas, RI, municipios, asociaciones civiles, pymes, clientes chicos y extremadamente grandes |
| Servicios que ofrece | Asesoramiento contable e impositivo periodico, planeamiento tributario, organizacion documental, presupuestos y control financiero, entes estatales y asociaciones civiles, certificacion Empresas B y planes sustentables |
| Software principal | Softcontador |
| Software secundario | Concilia Bot, Google Drive, Google Calendar, libretas a papel |
| Como recibe docs | WhatsApp, email, PDFs, fotografias, Excel, escaneado, bancos, carpetas compartidas de Drive |
| Peor dolor | Seguimiento documental, conseguir papeles, contabilidad y balance |
| Vencimientos | En la mente y papel. Nada automatizado. |
| Dinamica interna | "Conflictos entre lo nuevo y lo viejo" (el padre es tradicional, el quiere modernizar) |
| Perfil como cliente | **Dream client.** Sabe exactamente que problema tiene, lo comunica con claridad, piensa por etapas, prioriza seguridad, y ya confio documentacion real. |

---

## El problema real (segun Facundo)

> "El principal cuello de botella no esta en la parte tecnica contable, sino en la gestion documental, archivo, orden y trazabilidad de la informacion."

### Canales de entrada (7 canales distintos)

- WhatsApp
- Correo electronico
- PDFs
- Fotografias
- Excel
- Documentacion escaneada
- Canales informales varios

### Tareas manuales que hoy se hacen a mano

- Descarga de archivos uno por uno
- Clasificacion manual
- Movimiento entre carpetas
- Busquedas posteriores
- Duplicacion de documentacion
- Armado de papeles de trabajo
- Alta dependencia de control humano y memoria operativa

---

## Las 2 etapas que propone Facundo

### Etapa 1: Gestion documental (AHORA)

1.  **Centralizacion y organizacion documental**
2.  **Automatizacion del ingreso y clasificacion de archivos**
3.  **Integracion entre WhatsApp Web, correo electronico, Google Drive y agenda**
4.  **Estructura automatica de carpetas por cliente / periodo / tipo de documentacion**
5.  **Reduccion de tareas operativas repetitivas**
6.  **Trazabilidad documental y facilidad de busqueda**
7.  **Migracion progresiva hacia tareas de control, validacion y auditoria**
8.  **Alertas por vencimientos - Envio automatico de VEPs / liquidaciones de pago**

### Etapa 2: Dashboard de gestion (FUTURO)

- Situacion general de cada cliente
- Vencimientos impositivos con semaforo
- Documentacion pendiente
- Estados de cumplimiento
- Tareas abiertas
- Honorarios
- Balances pendientes
- Seguimiento operativo general
- Integracion con ARCA para datos automaticos

---

## Fases propuestas para Etapa 1

### Fase 1A (semana 1-2): Recepcion unificada

- Un numero/bot de WhatsApp exclusivo para recepcion de documentos
- Los clientes mandan ahi sus facturas, comprobantes, etc.
- El sistema clasifica automaticamente por cliente y tipo de documento
- Se almacena en Google Drive en la estructura de carpetas correcta

### Fase 1B (semana 3-4): Automatizacion de procesos

- Reglas de negocio para renombrado automatico de archivos
- Deteccion de documentacion faltante por cliente y periodo
- Alertas automaticas al cliente pidiendo lo que falta
- Envio de VEPs y recordatorios de vencimiento

### Fase 1C (semana 5-6): Trazabilidad y busqueda

- Panel simple donde ves el estado documental de cada cliente
- Busqueda por cliente, periodo, tipo de documento
- Duplicados detectados automaticamente

---

## Requisitos de seguridad (los puso Facundo explicitamente)

- Seguridad informatica
- Manejo de credenciales y permisos
- Modalidad de acceso a cuentas de clientes
- Trazabilidad de accesos
- Backups
- Cifrado en reposo y en transito
- Limites respecto del acceso automatizado a plataformas sensibles
- Arrancar con entorno de prueba y muestra acotada para validar antes de escalar

---

## Caso estrella: El municipio (420 facturas/mes)

### El problema

- Un cliente municipio genera 420 facturas/transacciones mensuales
- Facundo tiene que revisar cada una y pedir comprobantes si corresponde
- Recibe del banco los movimientos de dinero, pero las facturas/tickets son un desorden
- Hay dos firmantes que no revisan bien y pierden el hilo del dinero
- Al final el tiene que sacar balances y el reporte que debe presentar
- Ademas hacer "el saneamiento"

### Lo que necesita

- Ver las 420 transacciones del mes de un vistazo
- Saber cuales tienen factura y cuales no
- Pedir automaticamente los comprobantes faltantes
- Que los firmantes puedan revisar sin perderse
- Generar el reporte final

### Por que es un caso estrella

- Problema concreto y medible (420 facturas)
- Resultado claro (balances + reportes)
- Replicable a otros clientes
- Si lo resolves bien, Facundo te vende solo

---

## Lo que NO hacer

- No proponer un sistema complejo con login, password, dashboard lleno de cosas
- El pidio explicitamente: "algo que no le genere mas ruido, que simplifique, no una nueva capa de complejidad"
- Empezar con lo mas simple posible y agregar complejidad despues
- No prometer cosas que no se puedan cumplir

---

## Temas a definir con Facundo

- Alcance real de las automatizaciones posibles
- Integracion con Google Drive (su infraestructura existente)
- Modalidad de acceso a cuentas de clientes
- Que informacion de ARCA se puede integrar y hasta donde
- Formato de los entregables (reportes, dashboards)
- Periodicidad de las reuniones de seguimiento

---

## Proxima charla con Facundo: agenda

1.  Confirmar el enfoque por etapas
2.  Revisar la documentacion que compartio en Drive
3.  Definir los 2 o 3 clientes para el piloto
4.  Proponer arranque de Fase 1A la semana siguiente
5.  Hablar de seguridad y alcance

---

## Recordatorio

Facundo es el cliente ideal. Sabe lo que quiere, lo comunica bien, prioriza seguridad, y piensa en etapas. No le vendas humo — mostra resultados concretos y escalá desde ahi.

