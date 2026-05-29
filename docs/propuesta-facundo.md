# Analisis de viabilidad: Integracion con ARCA y otros organismos

---

## Lo que ofrece ARCA (web services oficiales)

ARCA expone web services publicos, pero estan diseñados para operaciones puntuales, no para alimentar dashboards en tiempo real.

| Web Service | Funcion | Apto para dashboard | Limitacion |
|-------------|---------|---------------------|------------|
| WSMTXCA | Consultar categoria de monotributo por CUIT | Si | Solo categoria actual, sin historial |
| WSConsulta | Obtener datos de inscripcion, actividad y regimen de un CUIT | Si | Datos publicos basicos, sin detalle |
| WSASS / WSCDC | Emision de comprobantes electronicos | No | Es para facturar, no para consultar |
| Domicilio Fiscal Electronico | Recepcion de notificaciones de ARCA | No | No tiene API publica. Hay que ingresar manualmente. |

### Que se puede obtener sin almacenar claves fiscales

- Categoria de monotributo actual
- Datos de inscripcion (actividad, impuestos habilitados)
- Estado de CUIT (activo, suspendido, excluido)

### Que NO se puede obtener via web service

- Detalle de facturacion emitida o recibida
- Deuda fiscal actualizada
- Movimientos de cuentas bancarias
- Notificaciones del Domicilio Fiscal Electronico
- DDJJ presentadas por el cliente
- Saldos a favor o a pagar

---

## Lo que ofrecen otros organismos

### Bancos

Algunas entidades exponen APIs abiertas (consulta de movimientos, saldos, resumenes). Sin embargo, requieren credenciales del cliente y autorizacion expresa. El nivel de esfuerzo de integracion por banco es alto y no es uniforme entre entidades.

### DPIP San Luis

No expone API publica para consulta automatica de deuda, presentaciones ni vencimientos. Las consultas se realizan mediante clave fiscal o tramite manual en el portal de Rentas.

### Municipalidad de San Luis

Sin API publica ni mecanismo de integracion automatica.

---

## Lo que es tecnicamente viable

| Funcionalidad | Viabilidad | Metodo |
|---------------|------------|--------|
| Consultar categoria de monotributo por CUIT | Alta | Web service oficial WSMTXCA |
| Consultar datos de inscripcion | Alta | Web service oficial WSConsulta |
| Vencimientos calendarizados | Alta | Calendario fiscal preconfigurado (ARCA + DPIP San Luis + Municipal) |
| Alertas de vencimiento | Alta | Calculo automatico sobre calendario preconfigurado |
| Dashboard con estado de cumplimiento | Media | Combinacion de datos automaticos + registro manual de presentaciones |

---

## Lo que no aconsejamos hacer

- Scraping automatizado del sitio de ARCA. El organismo bloquea IPs, cambia la estructura de las paginas sin previo aviso y la integracion es fragil y requiere mantenimiento constante.
- Automatizar la descarga de VEPs o boletos de pago. Implica gestionar credenciales de cada cliente, lo que introduce un riesgo de seguridad significativo.
- Almacenar claves fiscales de clientes en ningun sistema conectado a internet. Si se filtran, la responsabilidad recae sobre el estudio.
- Intentar integrar APIs bancarias en esta etapa. Cada banco tiene su propio esquema, muchas requieren convenios comerciales, y el esfuerzo de integracion es alto para el beneficio obtenido.

---

## Lo que si recomendamos

- Usar los web services oficiales de ARCA para datos publicos por CUIT (categoria, actividad, estado de inscripcion).
- Mantener un calendario fiscal preconfigurado y actualizable para los vencimientos de ARCA, DPIP San Luis y tasas municipales.
- Registrar el estado de presentacion de DDJJ de forma semiautomatica: el contador marca como presentado/pendiente/pagado en el dashboard, sin integracion directa con ARCA.
- Revisar manualmente el Domicilio Fiscal Electronico de cada cliente con periodicidad definida, y registrar las novedades en el sistema.

---

## Resumen

El dashboard puede integrar datos automaticos donde ARCA ofrece web services (categoria, actividad, estado de CUIT) y alimentarse de forma semiautomatica para el resto (presentaciones, vencimientos, documentacion pendiente). No es viable tecnicamente ni recomendable por seguridad intentar automatizar la consulta de facturacion, deuda o notificaciones del Domicilio Fiscal Electronico via scraping. El enfoque correcto es mixto: automatico donde se puede, semiautomatico donde no.
