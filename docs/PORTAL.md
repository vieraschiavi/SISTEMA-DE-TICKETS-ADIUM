# Cómo le pide algo la gente al área

En el portal de FreshService de IT, «Incidencia en = **Excelencia Comercial**» **no** es un pedido para nosotros:
es un pedido del área que **resuelve IT** (un acceso, un equipo, una aplicación). Si usáramos esa opción, los
pedidos de IT y los nuestros se mezclarían. Por eso la mesa tiene dos entradas propias, que terminan en el mismo
lugar:

| Entrada | Quién la usa | Qué necesita |
|---|---|---|
| **Portal de la mesa** («🌐 Portal», en la app y en la suite) | Cualquiera con su cuenta de Adium | Nada nuevo: es parte de la app |
| **Opción nueva en FreshService** («Reportería Excelencia Comercial») | El que ya está acostumbrado al portal de IT | Que IT agregue la opción y pase una API key |
| La casilla (`tickets.excelenciacomercial@…`) | Cualquiera, por correo | Ya está |
| La app de Power Apps (`powerapps/`) | Cualquiera, sin instalar nada | Armarla (guía de Power Platform) |

Todas crean el mismo ticket, con el mismo número `EC-00042`, el mismo SLA, el mismo tablero y la misma encuesta.

## 1 · El portal de la mesa

Es el portal de FreshService, pero para los pedidos a Excelencia Comercial & Digital:

- **Inicio** — tus pedidos abiertos, los que esperan tu respuesta y los que esperan tu conformidad; qué se le
  puede pedir al área, con el plazo habitual de cada tipo.
- **Enviar un ticket** — solicitante (tu cuenta), CC, tipo de pedido, mercado, tablero, asunto, descripción y
  adjuntos. Al costado, lo que necesitamos para resolverlo rápido según el tipo (el equivalente a los «artículos
  relacionados»), así el pedido no vuelve con «nos falta un dato».
- **Mis tickets** — con los chips de estado, «⏳ Esperando tu respuesta», la conversación (sólo lo público: las
  notas internas del equipo no se ven), responder con adjuntos y dar la conformidad (sí/no, de 1 a 5 y un
  comentario).

**Quién lo ve.** En modo compartido, una cuenta de Adium que **no** está en la lista Personas como analista o
coordinador ve **sólo** el portal; el equipo lo tiene como una página más. Cada uno ve únicamente sus pedidos y
los que lleva en copia: el filtro está en el motor (`Mesa.mis_tickets`, `Mesa.conversacion`), no en la pantalla.

> Para quien no tiene la suite, el mismo portal en Microsoft 365 es la app de Power Apps (pantallas «Nuevo
> pedido» y «Mis tickets», `powerapps/APP.md`): no se instala nada.

**Permisos en el modo compartido.** Para pedir desde el portal, la cuenta necesita permiso de **colaborar**
(agregar y editar elementos) en las listas Tickets, Eventos, Personas y Correos del sitio de la mesa: el pedido se
escribe con la cuenta de quien pide. Si el sitio queda en sólo lectura para el resto de Adium, el portal muestra
el error de permiso, y esa gente pide por la casilla o por Power Apps (que usa el mismo permiso). La PC de quien
sólo pide no lee la casilla, ni hace los cierres tácitos, ni habla con FreshService: eso lo corre el equipo.

**Lo que hay que saber del modo compartido.** La copia local de cada PC trae las listas enteras del sitio; el
portal muestra sólo lo propio, pero quien tiene lectura en el sitio de SharePoint puede ver los tickets ahí. Si
eso no sirve, el permiso del sitio se deja sólo para los dos equipos y la gente pide por Power Apps o por la
casilla.

## 2 · La opción en FreshService

### Lo que se le pide a IT

> **Asunto:** Nueva opción en «Incidencia en» para los pedidos a Excelencia Comercial
>
> Hola. Para que la gente pueda pedirle reportería y análisis a Excelencia Comercial & Digital desde el portal
> de FreshService (sin mezclarlo con los pedidos que el área le hace a IT), necesitamos:
>
> 1. Una opción nueva en el campo **«Incidencia en»** del formulario «Enviar un ticket»: **«Reportería
>    Excelencia Comercial»** (o el nombre que prefieran).
> 2. Que esa opción **no** se asigne a un grupo de IT (o que vaya a un grupo propio, «Mesa Excelencia
>    Comercial»).
> 3. Una **API key** de una cuenta con permiso para ver y actualizar esos tickets y agregarles notas (una cuenta de
>    servicio, si tienen). Nuestra mesa los trae cada pocos minutos, le devuelve a FreshService el estado
>    (abierto, pendiente, resuelto, cerrado) y deja la resolución como nota pública.
> 4. El **nombre de API** del campo «Incidencia en» (sale de `GET /api/v2/ticket_form_fields`), o el id del grupo
>    del punto 2.
>
> Gracias.

### Configurarlo

En `config.equipo.toml` (o `config.toml` de la PC que lo corre):

```toml
freshservice_activo = true
freshservice_dominio = "empresa.freshservice.com"
freshservice_campo = "incidencia_en"            # el nombre de API que pasó IT
freshservice_valor = "Reportería Excelencia Comercial"
# freshservice_filtro = "group_id:1234"          # en vez de campo y valor, si IT los manda a un grupo
```

y la clave **sólo por entorno**: `TICKETS_FRESHSERVICE_CLAVE`. La corre el proceso programado
(`scripts/procesar_casilla.py`, cada 5 minutos) o, en modo compartido, la PC que tenga la clave en su entorno: el
candado de la lista Correos evita que dos PCs importen el mismo ticket.

### Qué hace

| En FreshService | En la mesa |
|---|---|
| Alguien carga un ticket con la opción de la mesa | Entra como ticket nuevo, canal «FreshService», con el solicitante, los CC y la descripción; en FreshService queda una nota pública «Lo recibió … como EC-00042» |
| — | Se clasifica igual que un correo: tipo, prioridad, ATC, área terapéutica, unidad de negocio, equipo |
| Abierto (2) | Nuevo, Asignado, En curso, Reabierto |
| Pendiente (3) | En espera del solicitante |
| Resuelto (4) + la resolución como nota pública | Resuelto |
| Cerrado (5) | Cerrado (conforme o tácito) y Cancelado (con nota) |

Cada estado se devuelve una sola vez: lo que ya se mandó queda anotado en el historial del ticket (evento
«freshservice»).

### · REVISAR antes de prenderlo

Probado contra un doble de la API v2 (`tests/test_freshservice.py`), no contra el FreshService de Adium.

- `category` **no** se puede filtrar por la API: por eso se filtra por el nombre de API del campo «Incidencia en»
  o por el grupo.
- Si IT exige campos obligatorios para resolver o cerrar, el cambio de estado falla (queda el error en la
  pantalla 📨 Casilla y se reintenta en la próxima vuelta). La salida es que IT no los exija para esa opción.
- El solicitante sale de `/requesters/{id}` y, si es un agente de IT, de `/agents/{id}`. Hay que confirmar los
  dos con la cuenta de la API key.
- Los límites de la API van de 100 a 500 pedidos por minuto según el plan. Una vuelta usa unos pocos, salvo el
  primer día.
- La encuesta de conformidad de la mesa sale por correo también para estos tickets. Si FreshService manda la suya,
  el solicitante recibe dos: conviene apagar la de FreshService para esa opción.
