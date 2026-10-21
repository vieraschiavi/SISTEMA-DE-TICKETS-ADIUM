# Los seis flujos de Power Automate

Todos los flujos se crean **con la cuenta de servicio** (`svc-tickets-ec@…`) y
sólo usan conectores estándar. Los nombres de acciones van en castellano, como
los muestra Power Automate en español, con el nombre en inglés entre
paréntesis. Las columnas son los **nombres internos** de
`sharepoint/esquema.json`.

Las reglas son las mismas que las del motor (`tickets_ec/servicio.py`). Si un
flujo y el motor no coinciden, manda el motor y se corrige el flujo.

| # | Flujo | Disparador | Lo que hace |
|---|---|---|---|
| 1 | **Correo → ticket** | Llega un correo al buzón compartido | Crea el ticket o lo suma a uno abierto, clasifica y manda el acuse |
| 2 | **Avisos por evento** | Se crea un ítem en **Eventos** | Avisa al analista, pide el dato al solicitante, avisa la reapertura |
| 3 | **Encuesta de conformidad** | Se crea un Evento con `EstadoHasta = Resuelto` | Manda «¿Quedó conforme?» con botones y cierra o reabre según la respuesta |
| 4 | **Cierre tácito** | Recurrencia, todos los días hábiles a las 9:05 | Cierra lo resuelto sin respuesta después de `DiasTacita` días hábiles |
| 5 | **Vencidos del día** | Recurrencia, 9:15 | Manda al coordinador la lista de pendientes vencidos y por vencer |
| 6 | **Export para Power BI** | Recurrencia, 6:00 | Deja las listas como CSV para `exportar_powerbi.py --origen carpeta` |

> **Quién escribe un cambio de estado.** Lo escriben la app (pantalla de
> detalle) y los flujos 1, 3 y 4. Cada vez actualizan el ticket **y** crean el
> Evento en el mismo paso. Los avisos (flujo 2) se disparan por Eventos y no
> por el ticket: así ningún flujo necesita adivinar el valor anterior de
> «Estado».

---

## 1 · Correo → ticket

**Disparador:** *Cuando llega un nuevo correo electrónico a un buzón compartido
(V2)* (*When a new email arrives in a shared mailbox (V2)*).
- Dirección del buzón original: `tickets.excelenciacomercial@adium.com.uy`
- Carpeta: `Inbox` · Incluir datos adjuntos: **Sí** · Importancia: Cualquiera

**1.1 · Cortar los bucles.** Va primero. *Condición*: si alguna de estas es
verdadera, el flujo termina sin hacer nada (*Terminar* con estado «Correcto»):

```
equals(toLower(triggerOutputs()?['body/from']), 'tickets.excelenciacomercial@adium.com.uy')
or(startsWith(toLower(triggerOutputs()?['body/subject']), 'respuesta automática'),
   startsWith(toLower(triggerOutputs()?['body/subject']), 'automatic reply'),
   startsWith(toLower(triggerOutputs()?['body/subject']), 'resposta automática'),
   startsWith(toLower(triggerOutputs()?['body/subject']), 'fuera de la oficina'),
   startsWith(toLower(triggerOutputs()?['body/subject']), 'undeliverable'),
   startsWith(toLower(triggerOutputs()?['body/subject']), 'no se puede entregar'))
```

Además, en *Configuración* del disparador, en **Condiciones de desencadenador**:
`@not(equals(toLower(triggerOutputs()?['body/from']), 'tickets.excelenciacomercial@adium.com.uy'))`.

> Prueba: mandá un «fuera de la oficina» a la casilla. Tiene que aparecer una
> ejecución del flujo terminada sin crear nada.

**1.2 · Texto del correo.** *Html a texto* (*Html to text*, conector
Conversión de contenido) sobre `body/body` → `Texto`.
*Redactar* `TextoNormalizado` (minúscula y sin acentos, como `clasificador.normalizar`):

```
replace(replace(replace(replace(replace(replace(toLower(concat(triggerOutputs()?['body/subject'], ' ', body('Html_a_texto'))),'á','a'),'é','e'),'í','i'),'ó','o'),'ú','u'),'ñ','n')
```

**1.3 · ¿Es la respuesta a un ticket abierto?** *Redactar* `Numero`:

```
if(contains(triggerOutputs()?['body/subject'], '[EC-'),
   substring(triggerOutputs()?['body/subject'], add(indexOf(triggerOutputs()?['body/subject'], '[EC-'), 1), 8), '')
```

*Obtener elementos* (*Get items*), lista **Tickets**, consulta de filtro
`Numero eq '@{outputs('Numero')}'`, contar arriba: 1.

*Condición:* `Numero` no vacío **y** el ticket existe **y** su `Estado` no es
`Cerrado` ni `Cancelado`.

- **Sí → es una respuesta** (rama 1.4).
- **No → es un pedido nuevo** (rama 1.5). Si el número existía pero el ticket
  estaba cerrado, en la descripción va `(Seguimiento de EC-xxxxx)`.

**1.4 · Respuesta.**
1. *Crear elemento* en **Eventos**: `Title = correo_entrante`,
   `TicketNumero = Numero`, `En = utcNow()`, `Usuario = from`, `Publico = Sí` y
   `Detalle` con el texto de `Texto`.
2. Si `Estado = En espera del solicitante` y quien escribe **no** está en
   Personas con rol analista o coordinador: *Actualizar elemento* del ticket
   con `Estado = En curso`, `Subestado = En análisis` y `ActualizadoEn = utcNow()`.
   Después, *Crear elemento* en Eventos con `Title = estado`,
   `EstadoDesde = En espera del solicitante`, `EstadoHasta = En curso` y
   `Detalle = El solicitante respondió`.
3. Los adjuntos: *Aplicar a cada uno* sobre `attachments` → *Agregar datos
   adjuntos* (*Add attachment*) al ítem del ticket.

**1.5 · Pedido nuevo.**
1. **Quién pide:** *Obtener elementos* en **Personas** con
   `Mail eq '@{toLower(triggerOutputs()?['body/from'])}'`. Del primero salen
   `Area` y `Pais`. Si no está, `Area = Sin área` y el país sale del dominio
   (`.com.ar` → Argentina, etc., como `pais_por_dominio` en `config.py`); ese
   caso queda **a completar** por el equipo.
2. **Qué pide:** *Obtener elementos* en **ReglasClasificacion**, ordenar por
   `Peso desc`, arriba 500. *Filtrar matriz* (*Filter array*):
   `@contains(outputs('TextoNormalizado'), item()?['Title'])`. El primero
   da `Tipo` y `Equipo`. Sin coincidencias: `Tipo = Otro`, `Equipo = Excelencia Comercial`.
   > Es una versión simplificada del clasificador: toma la regla de mayor peso,
   > no la suma. Por eso el equipo revisa Tipo y Subtipo en la primera pasada.
3. **Sobre qué:** *Obtener elementos* en **Mercados** + *Filtrar matriz* con
   `@contains(outputs('TextoNormalizado'), toLower(item()?['Title']))`. El
   primero da `Mercado`, `ATC`, `AreaTerapeutica` y `UnidadNegocio`.
4. **Prioridad:** la del tipo, en la lista **SLA** con `Prioridad` = la del
   tipo. Si `TextoNormalizado` contiene `urgente` o `para hoy` → `Alta`; si
   contiene `critico` o `bloqueante` → `Crítica`.
5. *Crear elemento* en **Tickets**: `Title = subject`,
   `Descripcion = Texto`, `SolicitanteMail = toLower(from)`,
   `SolicitanteNombre` (de Personas o la parte antes de la `@`), `Area`,
   `Pais`, `Equipo`, `Tipo`, `Subtipo` (el primero de **Subtipos** del tipo),
   `Prioridad`, `Canal = Correo`, `Estado = Nuevo`, `Subestado = Sin
   clasificar`, `ATC`, `AreaTerapeutica`, `UnidadNegocio`, `Mercado`,
   `Cc = triggerOutputs()?['body/cc']`, `MessageId = triggerOutputs()?['body/internetMessageId']`,
   `CreadoEn = utcNow()`, `ActualizadoEn = utcNow()`, `Reaperturas = 0`,
   `VecesEnEspera = 0`, `Conformidad = Sin encuesta`, y en `Clasificacion` la
   regla que calzó, para que el analista vea por qué.
6. *Actualizar elemento*: `Numero = concat('EC-', formatNumber(outputs('Crear_elemento')?['body/ID'], '00000'))`.
7. *Crear elemento* en **Eventos**: `Title = estado`, `EstadoHasta = Nuevo`,
   `Detalle = Pedido recibido por correo`.
8. Los adjuntos, como en 1.4.
9. **Acuse:** *Enviar un correo electrónico desde un buzón compartido (V2)*
   (*Send an email from a shared mailbox (V2)*), desde la casilla, para `from`,
   con asunto `[EC-00042] <asunto original>`. El cuerpo es el de
   `plantillas.acuse`: número, tipo, prioridad y plazo estimado.

> Prueba: escribí «Necesito el share de rosuvastatina en Chile (IQVIA TAM)».
> Tiene que crear el ticket con Tipo «Pedido de información», ATC «C10»,
> Área terapéutica «Cardiovascular», Unidad de negocio «Gastro + Hipercol.»
> y mandarte un acuse con `[EC-…]` en el asunto. Respondé ese acuse y tiene
> que sumarse al mismo ticket, sin crear otro.

---

## 2 · Avisos por evento

**Disparador:** *Cuando se crea un elemento* (*When an item is created*), lista
**Eventos**. En las **condiciones de desencadenador**:
`@equals(triggerOutputs()?['body/Title'], 'estado')`.

*Obtener elementos* en **Tickets** con `Numero eq '@{triggerOutputs()?['body/TicketNumero']}'`.
Después, un *Switch* sobre `EstadoHasta/Value`:

| EstadoHasta | Correo (desde el buzón compartido) | Para |
|---|---|---|
| `Asignado` | «Te asignaron EC-… · asunto», con el link a la app `?ticket=EC-…` | el analista (`AnalistaMail`) |
| `En espera del solicitante` | «Para avanzar con EC-… necesitamos:» + `Detalle` (la pregunta) | el solicitante |
| `Reabierto` | «EC-… volvió: el solicitante no quedó conforme» + `Detalle` | el analista |
| `Cancelado` | «Cancelamos EC-…: » + `Detalle` (el motivo) | el solicitante |

Todos llevan `[EC-…]` en el asunto: así la respuesta vuelve al flujo 1.

---

## 3 · Encuesta de conformidad

**Disparador:** *Cuando se crea un elemento* en **Eventos**, con la condición
`@equals(triggerOutputs()?['body/EstadoHasta/Value'], 'Resuelto')`.

1. *Obtener elementos* del ticket, igual que en el flujo 2.
2. *Crear elemento* en **Encuestas**: `Title = Numero`, `Ronda = 1 + la
   cantidad de encuestas que ya tiene el ticket`, `EnviadaEn = utcNow()`,
   `Resultado = Pendiente`.
3. *Enviar correo electrónico con opciones* (*Send email with options*), para
   el solicitante, con asunto `[EC-…] ¿Quedó conforme con la resolución?`,
   el cuerpo con la `Resolucion` del ticket y estas opciones:
   `Conforme · 5 ★★★★★,Conforme · 4 ★★★★,Conforme · 3 ★★★,No conforme`.
   En *Configuración* de la acción, **Tiempo de espera** = `P5D`: cinco días
   corridos cubren los 3 hábiles más un fin de semana. El cierre exacto lo hace
   el flujo 4.
   > Este correo sale desde la cuenta de servicio: es lo que hace el conector,
   > y no puede salir desde el buzón compartido. Poné como nombre visible de la
   > cuenta «Tickets · Excelencia Comercial & Digital».
4. *Obtener elementos* del ticket **otra vez**. Si ya no está en `Resuelto`,
   porque respondió desde la app o lo cerró el flujo 4, se termina: la
   respuesta que llegó primero gana.
5. Si `SelectedOption` empieza con `Conforme`:
   - CSAT: `int(last(split(first(split(body('Enviar_correo_con_opciones')?['SelectedOption'], ' ★')), ' ')))`;
   - Encuestas: `Resultado = Conforme`, `CSAT` y `RespondidaEn`;
   - Tickets: `Estado = Cerrado`, `Subestado = Conforme`, `Conformidad = Conforme`, `CSAT` y `CerradoEn`;
   - Eventos: `estado` de `Resuelto` a `Cerrado`, con `Detalle = Conforme`.
6. Si es `No conforme`:
   - Encuestas: `Resultado = No conforme`;
   - Tickets: `Estado = Reabierto`, `Subestado = No conforme`, `Conformidad = No conforme` y `Reaperturas + 1`;
   - Eventos: `estado` de `Resuelto` a `Reabierto`. Ese Evento dispara el aviso al analista del flujo 2.
   - Para que cuente qué faltó: *Enviar un correo* desde la casilla pidiéndole
     que responda contando qué faltó. Su respuesta entra por el flujo 1 al
     mismo ticket.
7. **Si se agota el tiempo** (*Configurar ejecución posterior* → *se agotó el
   tiempo de espera*): no hace nada. El cierre tácito es del flujo 4, que
   cuenta días hábiles.

> Prueba: resolvé un ticket desde la app, elegí «Conforme · 4» en el correo y
> fijate que el ticket quede Cerrado con CSAT 4. Repetí con «No conforme»:
> tiene que quedar Reabierto, con `Reaperturas = 1`, y avisarle al analista.

---

## 4 · Cierre tácito

**Disparador:** *Periodicidad* (*Recurrence*), lunes a viernes a las 9:05, zona
`(UTC-03:00) Montevideo`.

1. *Obtener elementos* en **Encuestas** con `Resultado eq 'Pendiente'`.
2. *Obtener elementos* en **Feriados**, con `Fecha` desde hace 30 días.
3. Por cada encuesta: los **días hábiles** entre `EnviadaEn` y hoy son los días
   de lunes a viernes que no están en Feriados. Se calcula con un *Seleccionar*
   (*Select*) sobre `range(0, dateDifference)` y un *Filtrar matriz* por
   `dayOfWeek` entre 1 y 5 que no esté en Feriados. Si da `DiasTacita` (3) o más,
   y el ticket sigue en `Resuelto`:
   - Encuestas: `Resultado = Tácita`;
   - Tickets: `Estado = Cerrado`, `Subestado = Conformidad tácita`, `Conformidad = Tácita` y `CerradoEn`;
   - Eventos: `estado` de `Resuelto` a `Cerrado`, `Usuario = sistema`, `Detalle = Sin respuesta en 3 días hábiles`.

---

## 5 · Vencidos del día

**Disparador:** *Periodicidad*, lunes a viernes a las 9:15.

*Obtener elementos* en **Tickets** con
`(Estado eq 'Nuevo' or Estado eq 'Asignado' or Estado eq 'En curso' or Estado eq 'Reabierto') and VenceEn le '@{addHours(utcNow(), 9)}'`.
Después, *Crear tabla HTML* con Número, Asunto, Solicitante, Equipo, Analista,
Estado y Vence. Se manda desde la casilla a los coordinadores (Personas con
`Rol = coordinador`), con el asunto
`🚨 N tickets vencidos o por vencer · Excelencia Comercial & Digital`. Si la
lista está vacía, no se manda nada.

---

## 6 · Export para Power BI

**Disparador:** *Periodicidad*, todos los días a las 6:00.

Para cada lista (**Tickets**, **Eventos**, **Encuestas**, **Personas**):
1. *Obtener elementos*, con **paginación activada** (Configuración → Paginación → umbral 100000).
2. *Seleccionar* (*Select*) los **nombres internos** de `esquema.json` como
   encabezados. Las columnas de opción van con su `/Value`, por ejemplo
   `Estado: item()?['Estado/Value']`.
3. *Crear tabla CSV* → *Crear archivo* en la biblioteca **Export** del sitio,
   con el nombre `<Lista>.csv` y reemplazando el anterior.

En una PC del equipo con esa biblioteca sincronizada en OneDrive, el
Programador de tareas de Windows corre a las 6:30:

```bat
scripts\exportar_powerbi.bat --origen carpeta --csv "%USERPROFILE%\Adium\Tickets EC - Export"
```

Calcula las horas hábiles, el reloj detenido y el SLA con el mismo código que la
app, y escribe el Excel que lee el tablero. Con la app de Entra ID
(`Sites.Selected`), el mismo export lee las listas directo y este flujo no hace
falta: `--origen sharepoint`.
