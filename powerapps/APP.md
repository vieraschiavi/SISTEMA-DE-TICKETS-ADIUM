# La app de Power Apps: portal del solicitante + consola del equipo

Una sola app de lienzo, en formato **tableta**, con cinco pantallas. Sigue la
misma idea que el portal de IT (FreshService): un Inicio con tarjetas, «Sus
tickets» con un chip de estado, y un detalle con la conversación a la
izquierda y los **Datos del ticket** a la derecha. Los colores son los de la
suite Adium All in One.

## Antes de empezar

1. **Crear** → *Aplicación de lienzo en blanco* → formato Tableta → nombre
   «Tickets EC».
2. **Datos** → *Agregar datos* → SharePoint → sitio «Tickets EC». Se agregan
   las listas **Tickets, Eventos, Encuestas, Personas, Subtipos, SLA, Mercados,
   Feriados**.
3. **App** → propiedad **Formulas** → pegar entero `app/Formulas.fx`. Ese
   archivo se genera desde los catálogos y tiene los estados, las
   transiciones, los subestados, los colores y quién es del equipo.
4. **App** → **OnStart**:
   ```
   ClearCollect(colFeriados, Feriados);
   ClearCollect(colSLA, SLA);
   ClearCollect(colSubtipos, Subtipos);
   ClearCollect(colMercados, Mercados)
   ```
5. **Configuración → Próximas características**: verificá que esté activada
   la opción *Fórmulas con nombre*.

Cada pantalla lleva arriba el mismo **encabezado**: un rectángulo `Fill = Azul`
de alto 64, el logo de Adium (Multimedia → imagen), los botones de texto
INICIO · MIS TICKETS · CONSOLA (este último con `Visible = EsEquipo`) y, a la
derecha, el botón **Nuevo ticket** con `Fill = Rojo` y `Color = White`.

---

## 1 · scrInicio

| Control | Propiedad | Fórmula |
|---|---|---|
| `txtBuscar` | HintText | `"Buscá por número o asunto…"` |
| `txtBuscar` | OnChange | `Navigate(scrMisTickets, ScreenTransition.None, {buscar: txtBuscar.Text})` |
| `galTarjetas` (galería horizontal, 4 ítems) | Items | ver abajo |
| `galTarjetas` → `btnTarjeta` | OnSelect | `Navigate(ThisItem.Pantalla, ScreenTransition.Fade)` |
| `lblPendientes` | Text | `"Tenés " & CountRows(Filter(Tickets, SolicitanteMail = Yo && Estado.Value = "Resuelto")) & " pedido(s) esperando tu conformidad"` |

```
Filter(
    Table(
        {Titulo: "Mis tickets", Detalle: "Todos tus pedidos, respuestas y actividad", Icono: Icon.Note, Pantalla: scrMisTickets, Ver: true},
        {Titulo: "Nuevo pedido", Detalle: "Desarrollo, información, permisos o un problema", Icono: Icon.Add, Pantalla: scrNuevo, Ver: true},
        {Titulo: "Esperando mi conformidad", Detalle: "Pedidos resueltos que tenés que aprobar", Icono: Icon.CheckBadge, Pantalla: scrMisTickets, Ver: true},
        {Titulo: "Consola del equipo", Detalle: "Bandeja de Excelencia Comercial y Digital", Icono: Icon.People, Pantalla: scrConsola, Ver: EsEquipo}
    ),
    Ver
)
```

---

## 2 · scrNuevo: el formulario manda sobre el clasificador

Por el portal, el tipo lo elige quien pide. Por eso estos tickets llegan bien
clasificados y no hace falta adivinar.

| Control | Propiedad | Fórmula |
|---|---|---|
| `drpTipo` | Items | `Choices(Tickets.Tipo)` |
| `drpSubtipo` | Items | `Filter(colSubtipos, Tipo.Value = drpTipo.Selected.Value)` |
| `drpSubtipo` | Value (texto mostrado) | `Title` |
| `cmbMercado` (cuadro combinado, opcional) | Items | `colMercados` |
| `cmbMercado` | DisplayFields / SearchFields | `["Title"]` |
| `txtATC` | Default | `cmbMercado.Selected.ATC` |
| `drpUnidad` | Items | `UnidadesNegocio` |
| `drpUnidad` | Default | `Coalesce(cmbMercado.Selected.UnidadNegocio, "Transversal / no aplica")` |
| `drpArea` (área terapéutica) | Items | `AreasTerapeuticas` |
| `drpArea` | Default | `Coalesce(cmbMercado.Selected.AreaTerapeutica, "Transversal / no aplica")` |
| `drpFuente` | Items | `Choices(Tickets.FuenteDatos)` |
| `drpPrioridad` | Items | `Choices(Tickets.Prioridad)` |
| `drpPrioridad` | Default | `"Media"` |
| `txtAsunto`, `txtDescripcion`, `txtTablero` | — | texto (la descripción, multilínea) |
| `lblPlazo` | Text | `"Plazo estimado: " & Text(locVence, "dd/mm/yyyy")` |
| `btnEnviar` | DisplayMode | `If(IsBlank(txtAsunto.Text) || IsBlank(drpTipo.Selected), DisplayMode.Disabled, DisplayMode.Edit)` |

**`scrNuevo.OnVisible`**: `Reset(txtAsunto); Reset(txtDescripcion); Reset(cmbMercado)`

**Vence en días hábiles, con feriados.** `lblPlazo` necesita `locVence`.
Ponelo en `drpPrioridad.OnChange` y en `drpTipo.OnChange`:

```
UpdateContext({locVence:
    With({dias: LookUp(colSLA, Title = drpTipo.Selected.Value && Prioridad.Value = drpPrioridad.Selected.Value).DiasResolucion},
        DateAdd(
            Last(FirstN(
                Filter(ForAll(Sequence(dias * 2 + 15), DateAdd(Today(), Value, TimeUnit.Days)),
                       Weekday(Value, StartOfWeek.Monday) <= 5 && IsBlank(LookUp(colFeriados, DateValue(Fecha) = Value))),
                dias)).Value,
            HoraFin, TimeUnit.Hours))
})
```

**`btnEnviar.OnSelect`**: crea el ticket, le pone el número y deja el primer
evento.

```
With(
    {t: Patch(Tickets, Defaults(Tickets), {
        Title: txtAsunto.Text,
        Descripcion: txtDescripcion.Text,
        SolicitanteMail: Yo,
        SolicitanteNombre: User().FullName,
        Area: {Value: Coalesce(MiPersona.Area.Value, "Sin área")},
        Pais: {Value: Coalesce(MiPersona.Pais.Value, "Sin país")},
        Equipo: {Value: LookUp(colSLA, Title = drpTipo.Selected.Value).Equipo.Value},
        Tipo: {Value: drpTipo.Selected.Value},
        Subtipo: drpSubtipo.Selected.Title,
        Prioridad: {Value: drpPrioridad.Selected.Value},
        Canal: {Value: "Portal"},
        Estado: {Value: "Nuevo"},
        Subestado: "Sin clasificar",
        ATC: Upper(txtATC.Text),
        AreaTerapeutica: {Value: drpArea.Selected.Value},
        UnidadNegocio: {Value: drpUnidad.Selected.Value},
        Mercado: cmbMercado.Selected.Title,
        FuenteDatos: {Value: Coalesce(drpFuente.Selected.Value, "No aplica")},
        Tablero: txtTablero.Text,
        CreadoEn: Now(), ActualizadoEn: Now(), VenceEn: locVence,
        Reaperturas: 0, VecesEnEspera: 0,
        Conformidad: {Value: "Sin encuesta"},
        Clasificacion: "Elegido por el solicitante en el portal"
    })},
    With({numero: Prefijo & "-" & Text(t.ID, "00000")},
        Patch(Tickets, t, {Numero: numero});
        Patch(Eventos, Defaults(Eventos), {Title: "estado", TicketNumero: numero, En: Now(), Usuario: Yo,
              EstadoHasta: {Value: "Nuevo"}, Publico: true, Detalle: "Pedido recibido por el portal"});
        Notify("Creamos " & numero & ". Te va a llegar un correo con cada novedad.", NotificationType.Success);
        Navigate(scrDetalle, ScreenTransition.None, {locNumero: numero})
    )
)
```

> El acuse por correo de un pedido que entra por el portal lo puede mandar el
> flujo 2. Agregale el caso `EstadoHasta = Nuevo` con `Detalle` que empiece por
> «Pedido recibido por el portal».

---

## 3 · scrMisTickets

| Control | Propiedad | Fórmula |
|---|---|---|
| `drpVista` | Items | `["Abiertos o pendientes", "Esperando mi conformidad", "Todos"]` |
| `galTickets` | Items | ver abajo |
| `lblTitulo` | Text | `ThisItem.Title & " #" & ThisItem.Numero` |
| `lblSub` | Text | `"Creado el " & Text(ThisItem.CreadoEn, "ddd, dd mmm hh:mm") & " · Agente: " & Coalesce(LookUp(Personas, Mail = ThisItem.AnalistaMail).Title, "sin asignar")` |
| `lblChip` | Text | `Upper(ThisItem.Estado.Value)` |
| `lblChip` | Fill | `ColorValue(LookUp(ColoresEstado, Estado = ThisItem.Estado.Value).Fondo)` |
| `lblChip` | Color | `ColorValue(LookUp(ColoresEstado, Estado = ThisItem.Estado.Value).Letra)` |
| `lblChip` | RadiusTopLeft… (los 4) | `12` |
| `galTickets` | OnSelect | `Navigate(scrDetalle, ScreenTransition.None, {locNumero: ThisItem.Numero})` |

`galTickets.Items`, con todos los filtros delegables (`=` y `Or`):

```
SortByColumns(
    Filter(Tickets,
        SolicitanteMail = Yo,
        Switch(drpVista.Selected.Value,
            "Abiertos o pendientes", Estado.Value = "Nuevo" || Estado.Value = "Asignado" || Estado.Value = "En curso"
                || Estado.Value = "En espera del solicitante" || Estado.Value = "Resuelto" || Estado.Value = "Reabierto",
            "Esperando mi conformidad", Estado.Value = "Resuelto",
            true),
        IsBlank(locBuscar) || StartsWith(Numero, locBuscar) || StartsWith(Title, locBuscar)),
    "CreadoEn", SortOrder.Descending)
```

En **OnVisible**: `UpdateContext({locBuscar: buscar})`. `buscar` llega del Inicio.

---

## 4 · scrDetalle

**OnVisible**:
```
UpdateContext({locT: LookUp(Tickets, Numero = locNumero)});
UpdateContext({locUltimo: First(SortByColumns(Filter(Eventos, TicketNumero = locNumero, Title = "estado"), "En", SortOrder.Descending))})
```

**Banda de estado** (rectángulo `Fill = RGBA(255,244,214,1)`, como en FreshService):
```
locT.Estado.Value & " · " & locT.Subestado & "   desde hace " &
With({m: DateDiff(locUltimo.En, Now(), TimeUnit.Minutes)},
     If(m >= 1440, RoundDown(m / 1440, 0) & " días ", "") & RoundDown(Mod(m, 1440) / 60, 0) & " horas " & Mod(m, 60) & " minutos")
```

**Izquierda: la conversación.** El título es `"#" & locT.Numero & "  " & locT.Title`.
Debajo va `"Cc: " & locT.Cc`, y una galería con
`SortByColumns(Filter(Eventos, TicketNumero = locNumero, EsEquipo || Publico), "En", SortOrder.Ascending)`.
En cada ítem, `Usuario`, `Text(En, "dd/mm hh:mm")` y `Detalle`.

**Caja de respuesta** (`txtRespuesta`, multilínea) con **btnResponder.OnSelect**:
```
Patch(Eventos, Defaults(Eventos), {Title: "comentario", TicketNumero: locNumero, En: Now(), Usuario: Yo,
      Publico: !tglInterna.Value, Detalle: txtRespuesta.Text});
If(!EsEquipo && locT.Estado.Value = "En espera del solicitante",
   Patch(Tickets, locT, {Estado: {Value: "En curso"}, Subestado: "En análisis", ActualizadoEn: Now()});
   Patch(Eventos, Defaults(Eventos), {Title: "estado", TicketNumero: locNumero, En: Now(), Usuario: Yo,
         EstadoDesde: {Value: "En espera del solicitante"}, EstadoHasta: {Value: "En curso"}, Publico: true,
         Detalle: "El solicitante respondió"}));
Reset(txtRespuesta); Refresh(Eventos)
```
`tglInterna` (nota interna) lleva `Visible = EsEquipo`.

**Conformidad desde la app** (`Visible = !EsEquipo && locT.Estado.Value = "Resuelto"`):
un control **Calificación** `rtgCsat` (máximo 5) y dos botones.
- **btnConforme.OnSelect**:
  ```
  Patch(Tickets, locT, {Estado: {Value: "Cerrado"}, Subestado: "Conforme", Conformidad: {Value: "Conforme"},
        CSAT: rtgCsat.Value, CerradoEn: Now(), ActualizadoEn: Now()});
  Patch(Encuestas, First(SortByColumns(Filter(Encuestas, Title = locNumero), "EnviadaEn", SortOrder.Descending)),
        {Resultado: {Value: "Conforme"}, CSAT: rtgCsat.Value, RespondidaEn: Now()});
  Patch(Eventos, Defaults(Eventos), {Title: "estado", TicketNumero: locNumero, En: Now(), Usuario: Yo,
        EstadoDesde: {Value: "Resuelto"}, EstadoHasta: {Value: "Cerrado"}, Publico: true, Detalle: "Conforme"})
  ```
- **btnNoConforme** hace lo mismo con `Estado = Reabierto`, `Subestado = No
  conforme`, `Conformidad = No conforme`, `Reaperturas: locT.Reaperturas + 1`,
  y `Detalle` = lo que escribió en `txtRespuesta`, que es obligatorio. El
  flujo 3 encuentra el ticket ya fuera de «Resuelto» y no hace nada.

**Derecha: «Datos del ticket».** Con `DisplayMode = If(EsEquipo, DisplayMode.Edit, DisplayMode.View)`
en cada control:

| Control | Items | Default |
|---|---|---|
| `drpTipoD` | `Choices(Tickets.Tipo)` | `locT.Tipo.Value` |
| `drpSubtipoD` | `Filter(colSubtipos, Tipo.Value = drpTipoD.Selected.Value)` | `locT.Subtipo` |
| `drpEstadoD` | `Filter(Transiciones, Desde = locT.Estado.Value)` (columna `Hacia`), más el estado actual | `locT.Estado.Value` |
| `drpSubestadoD` | `Filter(SubestadosPorEstado, Estado = drpEstadoD.Selected.Hacia)` | `locT.Subestado` |
| `drpAnalistaD` | `Filter(Personas, Rol.Value = "analista" Or Rol.Value = "coordinador")` | `locT.AnalistaMail` |
| `drpEquipoD` | `Equipos` | `locT.Equipo.Value` |
| `drpPrioridadD`, `drpAreaD`, `drpPaisD`, `drpUnidadD`, `drpTerapeuticaD`, `drpFuenteD` | `Choices(Tickets.<columna>)` | el valor de `locT` |
| `txtATCD`, `txtMercadoD`, `txtTableroD`, `txtResolucionD` | — | el valor de `locT` |

**btnActualizar.OnSelect** (`Fill = Azul`, texto «Actualizar»):
```
With({nuevo: Coalesce(drpEstadoD.Selected.Hacia, locT.Estado.Value)},
    If(nuevo = "Resuelto" && IsBlank(txtResolucionD.Text),
        Notify("Contá qué se hizo: es lo que lee el solicitante antes de dar su conformidad.", NotificationType.Error),
        Patch(Tickets, locT, {
            Tipo: {Value: drpTipoD.Selected.Value}, Subtipo: drpSubtipoD.Selected.Title,
            Estado: {Value: nuevo}, Subestado: drpSubestadoD.Selected.Subestado,
            AnalistaMail: drpAnalistaD.Selected.Mail, Equipo: {Value: drpEquipoD.Selected.Value},
            Prioridad: {Value: drpPrioridadD.Selected.Value}, Area: {Value: drpAreaD.Selected.Value},
            Pais: {Value: drpPaisD.Selected.Value}, UnidadNegocio: {Value: drpUnidadD.Selected.Value},
            AreaTerapeutica: {Value: drpTerapeuticaD.Selected.Value}, FuenteDatos: {Value: drpFuenteD.Selected.Value},
            ATC: Upper(txtATCD.Text), Mercado: txtMercadoD.Text, Tablero: txtTableroD.Text,
            Resolucion: txtResolucionD.Text, ActualizadoEn: Now(),
            AsignadoEn: If(IsBlank(locT.AsignadoEn) && !IsBlank(drpAnalistaD.Selected.Mail), Now(), locT.AsignadoEn),
            PrimeraRespuestaEn: If(IsBlank(locT.PrimeraRespuestaEn) && nuevo in ["En curso", "En espera del solicitante", "Resuelto"], Now(), locT.PrimeraRespuestaEn),
            EnCursoEn: If(IsBlank(locT.EnCursoEn) && nuevo = "En curso", Now(), locT.EnCursoEn),
            ResueltoEn: If(nuevo = "Resuelto", Now(), locT.ResueltoEn),
            CanceladoEn: If(nuevo = "Cancelado", Now(), locT.CanceladoEn),
            VecesEnEspera: locT.VecesEnEspera + If(nuevo = "En espera del solicitante" && locT.Estado.Value <> nuevo, 1, 0),
            Conformidad: If(nuevo = "Resuelto", {Value: "Pendiente"}, locT.Conformidad)
        });
        If(nuevo <> locT.Estado.Value,
            Patch(Eventos, Defaults(Eventos), {Title: "estado", TicketNumero: locNumero, En: Now(), Usuario: Yo,
                  EstadoDesde: {Value: locT.Estado.Value}, EstadoHasta: {Value: nuevo}, Publico: true,
                  Detalle: If(nuevo = "Resuelto", txtResolucionD.Text, txtRespuesta.Text)}));
        If(drpAnalistaD.Selected.Mail <> locT.AnalistaMail,
            Patch(Eventos, Defaults(Eventos), {Title: "asignacion", TicketNumero: locNumero, En: Now(), Usuario: Yo,
                  Detalle: Coalesce(locT.AnalistaMail, "sin asignar") & " → " & drpAnalistaD.Selected.Mail}));
        UpdateContext({locT: LookUp(Tickets, Numero = locNumero)});
        Notify("Ticket actualizado.", NotificationType.Success)
    )
)
```

> Las reglas de la app son las del motor: el equipo no puede pasar un ticket a
> «Cerrado». `Transiciones` no lo ofrece, porque «Resuelto → Cerrado» lo decide
> el solicitante. «En espera» detiene el reloj (lo mide el export), y para
> resolver hay que escribir qué se hizo.

---

## 5 · scrConsola (sólo el equipo)

`OnVisible`: `If(!EsEquipo, Navigate(scrInicio))`.

Una fila de filtros: `drpEquipoF` (`Equipos`, con su valor por defecto en el
equipo de `MiPersona.Area.Value`) y `drpEstadoF`, con los valores
«Pendientes del equipo», «Esperando al solicitante», «Vencidos» y «Todos».
También `drpTipoF`, `drpAreaF`, `drpUnidadF` y `drpAnalistaF`, cada uno con un
primer valor «(todos)».

`galBandeja.Items`:
```
SortByColumns(
    Filter(Tickets,
        Equipo.Value = drpEquipoF.Selected.Value,
        Switch(drpEstadoF.Selected.Value,
            "Pendientes del equipo", Estado.Value = "Nuevo" || Estado.Value = "Asignado" || Estado.Value = "En curso" || Estado.Value = "Reabierto",
            "Esperando al solicitante", Estado.Value = "En espera del solicitante" || Estado.Value = "Resuelto",
            "Vencidos", (Estado.Value = "Nuevo" || Estado.Value = "Asignado" || Estado.Value = "En curso" || Estado.Value = "Reabierto") && VenceEn < Now(),
            true),
        drpTipoF.Selected.Value = "(todos)" || Tipo.Value = drpTipoF.Selected.Value,
        drpAreaF.Selected.Value = "(todos)" || Area.Value = drpAreaF.Selected.Value,
        drpUnidadF.Selected.Value = "(todos)" || UnidadNegocio.Value = drpUnidadF.Selected.Value,
        drpAnalistaF.Selected.Value = "(todos)" || AnalistaMail = drpAnalistaF.Selected.Value),
    "VenceEn", SortOrder.Ascending)
```

En cada ítem:
- el asunto;
- el solicitante con su área;
- `Tipo.Value & " · " & Subtipo`;
- `ATC & " · " & UnidadNegocio.Value`;
- el analista;
- el chip de estado de scrMisTickets;
- el **semáforo**: un círculo con
  `Fill = If(VenceEn < Now(), ColorValue("#E03131"), DateDiff(Now(), VenceEn, TimeUnit.Hours) < 9, ColorValue("#FAB005"), ColorValue("#12B886"))`.

> `drpTipoF.Selected.Value = "(todos)" || …`: la parte izquierda no depende de
> la fila, así que Power Apps la resuelve antes de mandar el filtro a
> SharePoint y la consulta sigue siendo delegable. Si aparece el subrayado azul
> de delegación, el filtro que lo provoca es el que hay que reescribir.

---

## Probar antes de compartir

1. Como solicitante (una cuenta que no esté en Personas): crear un pedido de
   cada tipo y verlos en «Mis tickets» con su chip.
2. Como analista: tomarlo, pedir un dato, responder desde la otra cuenta y
   comprobar que vuelve a «En curso». Después, resolverlo.
3. Responder la encuesta por correo **y** desde la app, en dos tickets
   distintos. Los dos tienen que quedar Cerrados, con CSAT.
4. Correr `scripts/exportar_powerbi.bat --origen carpeta …` y abrir el
   tablero. Los tickets de la prueba tienen que estar, con sus tiempos.
