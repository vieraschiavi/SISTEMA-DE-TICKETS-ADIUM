# Tickets · Excelencia Comercial & Digital

**Versión 1.2.1 · 2026-11-05** — Pedidos por correo · seguimiento · SLA · conformidad · Power BI

> Generado por `python scripts/documentar.py` desde el programa: no se edita a mano. La versión para proyectar es `docs/PROYECTO.html`.

## En una página

- **Qué resuelve.** Que cada pedido a Excelencia Comercial y a Digital tenga dueño, plazo y respuesta, y que se pueda medir: cuántos entran, quién tiene cada uno, cuánto tardan y si el que pidió quedó conforme.
- **Qué es.** Una mesa de pedidos: cada pedido es un ticket con número, solicitante, área, tipo, unidad de negocio y ATC, analista, estados con fecha y hora, plazo en horas hábiles y encuesta de conformidad.
- **Cómo entra.** Por 6 canales que terminan en el mismo ticket: la casilla, el portal propio, FreshService de IT, Power Apps o el equipo a mano.
- **Cómo se mide.** Un tablero de Power BI con cada indicador verificado contra la app antes de entregarse, listo para publicar en el workspace del área o en Fabric.
- **Dónde corre.** En la PC de cada integrante (sola o dentro de la suite Adium All in One) sobre las mismas listas de SharePoint, o entera en Microsoft 365 (Power Apps + Power Automate).

## Cómo entra un pedido

| Canal | Cómo entra |
|---|---|
| Correo | Un correo a la casilla del área. La respuesta del solicitante se suma al mismo ticket por el número del asunto; los automáticos («fuera de la oficina») no abren nada. |
| Portal | El portal de la mesa (🌐 Portal), en la app o en la suite, con la cuenta de Adium: Enviar un ticket, Mis tickets y la conformidad. |
| Manual | El equipo lo carga en «➕ Nuevo pedido» cuando el pedido llegó de palabra. |
| Teams | El equipo lo carga desde una conversación de Teams. |
| Teléfono | El equipo lo carga desde una llamada. |
| FreshService | La opción de la mesa en el portal de IT («Reportería Excelencia Comercial»); el estado y la resolución vuelven a FreshService. Apagado hasta que IT sume la opción. |

Todos los canales crean el mismo ticket, con el mismo número (`EC-00042`), la misma clasificación automática, el mismo plazo y la misma encuesta.

## Qué le pasa a un pedido

| Estado | Subestados | Desde acá el equipo lo pasa a | Reloj del plazo |
|---|---|---|---|
| Nuevo | Sin clasificar | Asignado, En curso, En espera del solicitante, Resuelto, Cancelado | corre |
| Asignado | En cola del analista | En curso, En espera del solicitante, Resuelto, Cancelado | corre |
| En curso | En análisis, En desarrollo, Esperando a IT / fuente de datos, En validación de datos, En aprobación | En espera del solicitante, Resuelto, Cancelado | corre |
| En espera del solicitante | Esperando información, Esperando aprobación del solicitante, Esperando validación | En curso, Resuelto, Cancelado | detenido |
| Resuelto | Esperando conformidad | lo decide el solicitante (o el cierre tácito) | detenido |
| Reabierto | No conforme | En curso, En espera del solicitante, Resuelto, Cancelado | corre |
| Cerrado | Conforme, Conformidad tácita | — | — |
| Cancelado | Duplicado, Fuera de alcance, Lo retiró el solicitante | — | — |

Mientras se espera al solicitante, el reloj se detiene. Al resolverlo, el solicitante recibe «¿Quedó conforme?» con una nota de 1 a 5. Si dice que no, el ticket se reabre; si no contesta en 3 días hábiles, se cierra con conformidad tácita. El día hábil va de 9 a 18 h, sin feriados de Uruguay.

## Qué se puede pedir y en cuánto tiempo

| Tipo de pedido | Lo atiende | Prioridad habitual | Días hábiles (Crítica · Alta · Media · Baja) | Por ejemplo |
|---|---|---|---|---|
| Incidente / dato incorrecto | Excelencia Comercial | Alta | 1 · 2 · 3 · 5 | Dato incorrecto o que no cierra, Tablero que no actualiza, Visual o tablero con error, Fuente de datos caída |
| Solicitud de permisos | Excelencia Comercial | Alta | 1 · 1 · 2 · 3 | Acceso a app o workspace de Power BI, Acceso por país o marca (RLS), Acceso a fuente de datos (MDW / Fabric / SQL), Acceso a Adaptive, Licencia Power BI Pro / Copilot |
| Nuevo desarrollo | Excelencia Comercial | Media | 5 · 10 · 20 · 30 | Tablero Power BI nuevo, Modelo de datos o medidas DAX, Automatización o proceso de datos, Presentación o mazo |
| Cambio en tablero existente | Excelencia Comercial | Media | 2 · 5 · 8 · 15 | Agregar KPI o columna, Filtros o segmentadores, Nueva página, Formato o diseño |
| Pedido de información | Excelencia Comercial | Media | 1 · 3 · 5 · 10 | Mercado conformado, Consulta de mercado (IQVIA), Recetas y médicos (Close Up), Venta interna / PEA, Extracción de base, Dato puntual |
| Pedido digital | Digital | Media | 1 · 3 · 5 · 10 | CRM / Veeva, Campaña o canal digital, Web, app o e-detailing, Analítica digital |
| Capacitación / consulta | Excelencia Comercial | Baja | 1 · 3 · 5 · 10 | Uso de un tablero, Power BI / DAX, Fuentes de datos |
| Otro | Excelencia Comercial | Media | 1 · 3 · 5 · 10 |  |

Primera respuesta del equipo: Crítica 2 h · Alta 4 h · Media 9 h · Baja 18 h hábiles.

## Clasificación automática

- **Tipo, subtipo y prioridad**, por las palabras del asunto y la descripción (con el porqué, a la vista del equipo); las urgencias suben la prioridad.
- **Equipo resolutor:** Excelencia Comercial o Digital; lo digital (CRM, Veeva, mailing, landing…) va a Digital, y un pedido se puede derivar entre los dos.
- **ATC y mercado conformado de HQ**, y de ahí el **área terapéutica** (Metab & Obesidad, Cardiovascular, Aparato Digestivo, Neurociencias, Osteo Dolor, Salud de la Mujer, Salud del Hombre, Oncología, Otra, Transversal / no aplica) y la **unidad de negocio** (Cardiovascular, Gastro + Hipercol., Metab & Obesidad Lic, Metab & Obesidad Pr, Neurociencias, Osteo Dolor, Salud de la Mujer, Salud del Hombre, Oncología, Otra, Transversal / no aplica).
- **Área y país** del solicitante, por el directorio y el dominio de su correo; **fuente de datos** (IQVIA, Close Up, Venta interna / Adaptive, Stocking, Non Retail, MDW / Analysis Services, Fabric, Otra, No aplica).

## Quién hace qué

| Rol | Puede |
|---|---|
| Coordinador | Todo: asignar y reasignar, derivar, dar de alta y de baja integrantes. |
| Analista | Tomar lo que está sin asignar, trabajar y resolver lo suyo, dejar notas en cualquier ticket, leer la casilla. |
| Cualquier cuenta de Adium | Pedir por el portal, la casilla, FreshService o Power Apps, seguir sus pedidos y dar la conformidad. |

En el modo compartido el rol sale de la lista **Personas**. La app nunca ve una contraseña: el ingreso es la página de Microsoft, con el MFA de Adium.

## Indicadores

### Volumen

| Indicador | Qué mide |
|---|---|
| Tickets recibidos | Pedidos que entraron en el período (por fecha de creación). |
| Tickets resueltos | Pedidos resueltos en el período (por fecha de resolución, entren cuando entren). |
| Backlog fin de período | Pedidos que al último día del período habían entrado y todavía no estaban resueltos ni cancelados. |
| Pendientes del equipo | Hoy en Nuevo, Asignado, En curso o Reabierto (corre el reloj del SLA). |
| Pendientes por antigüedad | Pendientes del equipo, sin las categorías vacías (para el gráfico por antigüedad). |
| Vencidos sin resolver | Pendientes del equipo que ya pasaron su SLA. |
| Vencido (pendientes) | Vencidos sin resolver, en blanco para lo que no está pendiente: la tabla de abiertos muestra sólo abiertos. |
| Cancelados | Pedidos cancelados (duplicados, fuera de alcance o retirados). |
| Solicitantes | Personas distintas que pidieron. |
| Áreas que piden | Áreas solicitantes distintas con al menos un pedido. |

### Tiempos y SLA

| Indicador | Qué mide |
|---|---|
| % en SLA | De los resueltos, cuántos en el plazo de su tipo y prioridad (horas hábiles, sin el tiempo en espera del solicitante). |
| % respuesta en SLA | Primera respuesta del equipo dentro del plazo de su prioridad. |
| Horas primera respuesta | Horas hábiles hasta que el equipo respondió o empezó. |
| Días de resolución | Días hábiles efectivos de la creación a la resolución (sin la espera del solicitante). |
| Días de resolución (mediana) | La mitad se resolvió en menos de esto: no la mueven los pocos pedidos larguísimos. |
| SLA en días | El plazo de resolución acordado (matriz tipo × prioridad). |
| Días abierto | Días hábiles efectivos que llevan abiertos los pendientes. |
| Horas en estado | Horas hábiles promedio que un ticket pasa en cada estado. |
| Pasos por el estado | Cuántas veces un ticket entró al estado. |

### Conformidad

| Indicador | Qué mide |
|---|---|
| Tasa de reapertura | Resueltos que el solicitante devolvió al menos una vez («No conforme»). |
| % sin idas y vueltas | Resueltos sin pedir datos al solicitante y sin reaperturas. |
| Encuestas enviadas | Encuestas de conformidad enviadas (una por cada resolución, incluidas las de tickets reabiertos). |
| Conformes | Encuestas respondidas «Sí, conforme». |
| No conformes | Encuestas respondidas «No, falta algo»: cada una reabre el ticket. |
| Conformidad tácita | Cerrados sin respuesta a la encuesta en los días hábiles de gracia. |
| % de respuesta a la encuesta | Encuestas respondidas sobre encuestas cerradas (respondidas + tácitas). |
| % conformidad | De los que respondieron la encuesta, cuántos quedaron conformes. |
| % conformidad con tácita | Cuenta como conforme el silencio después de los días de gracia. |
| Satisfacción (1 a 5) | Promedio de la nota de 1 a 5 que dejó el solicitante en la encuesta. |
| % satisfechos (4 y 5) | De las notas de satisfacción, cuántas fueron 4 o 5. |
| Índice de efectividad | 40 % cumplir el plazo + 40 % conformidad (con tácita) + 20 % que no vuelva (1 − reapertura). |

## El tablero de Power BI (8 páginas)

| Página | La pregunta que contesta |
|---|---|
| Resumen ejecutivo | ¿Cuánto entra, cuánto sale y con qué calidad? |
| Tickets mensuales | ¿Entra más de lo que sale? ¿Crece el backlog? |
| Quién pide | ¿De quién, de qué área y de qué país llegan los pedidos? |
| Qué piden | ¿Qué tipo de pedido, de qué área terapéutica, ATC y mercado? |
| Tiempos y SLA | ¿Respondemos y resolvemos en el plazo acordado? |
| Equipo | ¿Cómo se reparte la carga y cómo rinde cada analista? |
| Conformidad | ¿Quedan conformes quienes piden? |
| Backlog y antigüedad | ¿Qué está abierto, desde cuándo y de quién es? |

Cada indicador del tablero tiene su gemelo en la app (`indicadores.kpis`): el armado del `.pbit` compara los dos y no entrega si difieren. Sale como `.pbit` (se abre en Power BI Desktop y se publica), como proyecto PBIP para Fabric con Git, o se publica por API.

## Dónde corre

| Modo | Para qué | Dónde viven los tickets |
|---|---|---|
| Local | Una PC sola, el piloto o la demo | Un SQLite en esa PC |
| Compartido | Cada integrante en su PC, con su cuenta de Adium | Las listas de SharePoint de la mesa (cada PC con su copia) |
| Power Platform | Todo en Microsoft 365, sin instalar nada | Las mismas listas de SharePoint |

En el modo compartido, cada escritura va primero a la lista con la versión que esa PC leyó: si dos personas tocan el mismo ticket, la segunda recibe «otro integrante lo cambió» y nada se pisa. El mismo correo leído por dos PCs abre un solo ticket.

### Llevarla a Power Platform

1. **Pedirle a IT el buzón, la cuenta de servicio y el sitio** — Correo a IT · 1 pedido
2. **Crear las 10 listas de SharePoint** — PowerShell 7 + PnP.PowerShell · 10 min
3. **Cargar el equipo en la lista Personas** — SharePoint · 10 min
4. **Conectar la app de cada integrante a la misma mesa** — IT (Entra ID) + config.equipo.toml · 30 min
5. **Crear los 6 flujos de Power Automate** — Power Automate (con la cuenta de servicio) · 2-3 h
6. **Armar la app de Power Apps** — Power Apps Studio · 1 día
7. **Publicar y compartir la app** — Power Apps · 5 min
8. **Programar el export diario y publicar el tablero** — PC del equipo + Power BI · 30 min
9. **Prueba de punta a punta** — Todo junto · 30 min

### FreshService de IT

«Incidencia en = Excelencia Comercial» es un pedido del área que resuelve IT. Para los pedidos A la mesa, IT suma una opción propia y el conector (apagado por defecto) los trae; el estado vuelve:

| En la mesa | En FreshService |
|---|---|
| Nuevo | Abierto |
| Asignado | Abierto |
| En curso | Abierto |
| En espera del solicitante | Pendiente |
| Resuelto | Resuelto |
| Reabierto | Abierto |
| Cerrado | Cerrado |
| Cancelado | Cerrado |

## Seguridad y datos

- Los conectores (envío de correo, FreshService) salen **apagados**; los secretos van sólo por variables de entorno (`TICKETS_*`) y un `.toml` con un secreto no arranca.
- Ninguna contraseña pasa por la app: el ingreso es el de Microsoft y el token vive en memoria.
- En el portal cada uno ve sólo sus pedidos y los que lleva en copia; el filtro está en el motor.
- Lo que escribe el solicitante se escapa antes de entrar a un correo o a una pantalla.
- La demo es 100 % sintética: personas ficticias en un dominio que no existe.

## El programa por dentro

| Módulo | Qué hace |
|---|---|
| `acceso.py` | Quién está usando la app: el ingreso con la cuenta de Microsoft de Adium y lo que cada rol puede hacer. |
| `almacen.py` | Dónde viven los tickets: SQLite, con el mismo esquema que `sql/01_esquema.sql` crea en SQL Server. |
| `catalogos.py` | Los catálogos de la mesa: estados, tipos de pedido, prioridades con su SLA, áreas y países de Adium. |
| `clasificador.py` | Del correo al ticket: qué tipo de pedido es, qué prioridad tiene y de qué área y país viene quien lo manda. |
| `compartida.py` | El modo compartido: seis PCs, una sola mesa. |
| `config.py` | La configuración de la mesa: casilla, URL de la app, calendario laboral y conectores de correo. |
| `correo.py` | El correo de la casilla: leerlo, entender si es un pedido nuevo o la respuesta a uno abierto, y escribir lo que la mesa contesta. |
| `demo.py` | Dieciocho meses de pedidos, simulados con semilla fija y pasando por la MISMA mesa que usa la app. |
| `exportar.py` | El modelo estrella que lee Power BI: cuatro tablas, una fila = un hecho. |
| `freshservice.py` | FreshService de IT ↔ la mesa. |
| `guia.py` | La guía para llevar la mesa a Power Platform, como datos. |
| `indicadores.py` | Los indicadores de efectividad de la mesa, con UNA definición. |
| `marca.py` | La marca de la suite Adium All in One, para que la mesa de tickets se vea como el informe de al lado. |
| `plantillas.py` | Los correos que manda la mesa, con la marca de Adium. |
| `servicio.py` | La mesa: todo lo que le puede pasar a un ticket, en un solo lugar. |
| `sharepoint.py` | La mesa en Microsoft 365: las listas de SharePoint que usan Power Apps y Power Automate, y su lectura para el tablero de Power BI. |
| `sla.py` | El reloj de la mesa: horas hábiles, vencimientos y cumplimiento de SLA. |

La app (Streamlit) tiene estas páginas: 🏠 Inicio · 📥 Bandeja · 🎫 Ticket · ➕ Nuevo pedido · 📨 Casilla · 📊 Indicadores · 📤 Power BI · 🧭 Guía Power Platform · ⚙️ Configuración · 🌐 Portal. Todo lo que cambia un ticket pasa por `servicio.Mesa`: la app, el portal, la casilla, FreshService y la demo usan las mismas reglas.

**110 pruebas** en 19 archivos (`python -m pytest -q tests`), el linter (`ruff check .`) y una recorrida de la app de verdad en Chromium (`python scripts/e2e_ui.py`).

## Qué falta probar en el tenant de Adium

- El modo compartido con dos cuentas reales (está probado contra un doble de SharePoint): `docs/EQUIPO.md`.
- La opción de FreshService y su API key (probado contra un doble de la API v2): `docs/PORTAL.md`.
- Los flujos de Power Automate y la app de Power Apps: la guía de Power Platform.

## Historial de versiones

### 1.2.1 · 2026-11-05 · Arreglos de Inicio y Bandeja

- «Abrir» en Inicio y elegir una fila de la Bandeja rompían con `StreamlitWidgetAlreadyInstantiatedError`: la página se cambiaba después de dibujar el selector de la barra lateral. Ahora se pide para la próxima corrida y se aplica antes de dibujarlo.
- La Bandeja con el filtro «Estado» vacío y una búsqueda rompía con `KeyError: 'Creado'`. Un filtro vacío ahora es «todos» (como los demás) y la búsqueda ya no se queda sin columnas cuando no hay filas.
- Pruebas nuevas que recorren la app de verdad en modo local (`tests/test_app_local.py`): Abrir desde Inicio, la Bandeja con Estado vacío y una búsqueda sin resultados.

### 1.2.0 · 2026-11-05 · Portal propio y FreshService

- **Portal del solicitante** (🌐 Portal), al estilo del portal de FreshService de IT: Inicio, Enviar un ticket y Mis tickets, con la conversación, las respuestas con adjuntos y la conformidad. Quien entra con su cuenta de Adium y no es del equipo ve sólo el portal, y cada uno ve únicamente lo suyo.
- **Conector con FreshService** (apagado por defecto). «Incidencia en = Excelencia Comercial» es un pedido nuestro que resuelve IT, así que IT suma una opción propia («Reportería Excelencia Comercial»). Lo que entra por ahí llega a la mesa, y el estado y la resolución vuelven a FreshService. El texto del pedido a IT está en `docs/PORTAL.md`.
- **Documentación del proyecto que se regenera con cada versión** (`docs/PROYECTO.md` y `docs/PROYECTO.html`, para presentar).
- Ayuda por tipo de pedido en el portal (`catalogos.AYUDA`) y canal «FreshService».

### 1.1.0 · 2026-10-21 · Modo compartido

- Cada integrante del equipo, en su PC (sola o dentro de la suite Adium All in One), entra con su cuenta de Microsoft de Adium y trabaja sobre las mismas listas de SharePoint, que alimenta la casilla.
- Escrituras con eTag: si dos personas tocan el mismo ticket, la segunda recibe «otro integrante lo cambió» y nada se pisa. Hay una cola para cuando se corta la red y un candado para que el mismo correo no abra dos tickets.
- Roles desde la lista Personas. Encuesta de conformidad contestada por correo. `config.equipo.toml` sin secretos.
- El `.bat` ya no se abre y se cierra: consigue Python, instala lo que falta y dice qué falló.

### 1.0.0 · 2026-10-21 · La mesa

- Casilla de correo → ticket con solicitante, área, país, tipo, subtipo, prioridad, ATC, área terapéutica, unidad de negocio y equipo resolutor (Excelencia Comercial o Digital), clasificados automáticamente.
- Estados con fecha y hora, subestados, SLA en horas hábiles con el reloj detenido mientras se espera al solicitante, y encuesta de conformidad con cierre tácito.
- Tablero de Power BI de 8 páginas, con cada KPI verificado contra la app; `.pbit`, PBIP para Fabric y publicación por API.
- Paquete de Power Platform (listas de SharePoint, flujos, app de Power Apps) generado desde los mismos catálogos, y la guía paso a paso dentro de la app y de la suite.
