# La mesa en Power Platform (entorno corporativo)

El camino recomendado para Adium: corre con las licencias de Microsoft 365 que
ya tiene la gente. Se entra con el usuario de Microsoft y no hay que instalar
nada ni mantener un servidor. IT lo gobierna como cualquier otra app del tenant.

```
 Solicitante ──correo──►  Buzón compartido  ──►  Power Automate  ──►  Listas de SharePoint  ◄──  Power Apps
 (cualquier área)        tickets.excelencia…     (6 flujos)           (Tickets, Eventos,          (portal del
              └─portal──────────────────────────────────────────────►  Encuestas, Personas…)       solicitante +
                                                                              │                     consola del
                                                                              ▼                     equipo)
                                                     exportar_powerbi.py --origen sharepoint (1 vez por día)
                                                                              ▼
                                                     Excel del modelo estrella ──► Power BI (.pbix / Fabric)
```

| Pieza | Qué hace | Licencia |
|---|---|---|
| **Buzón compartido** de Exchange Online | Recibe los pedidos por correo y manda las respuestas | sin licencia propia (buzón compartido < 50 GB) |
| **Listas de SharePoint** (9) | La base: tickets, cada cambio de estado, encuestas, personas y catálogos | incluida en M365 |
| **Power Automate** (6 flujos) | Correo → ticket, avisos, encuesta de conformidad, cierre tácito, recordatorios | conectores **estándar**: Office 365 Outlook, SharePoint, Aprobaciones/Correo con opciones, Conversión de contenido |
| **Power Apps** (app de lienzo) | Portal tipo FreshService para pedir y seguir, y consola del equipo | incluida en M365 (sólo conectores estándar) |
| **Power BI** | El tablero (`powerbi/`) | Pro o Fabric para publicar y compartir |

**No hace falta ninguna licencia premium.** Todo usa conectores estándar y
SharePoint (no Dataverse). Si en el futuro se pasa a Dataverse, el esquema de
`sharepoint/esquema.json` es el mismo.

## Qué pedir a IT (un solo pedido)

1. **Buzón compartido** `tickets.excelenciacomercial@adium.com.uy`, con nombre
   visible «Tickets · Excelencia Comercial & Digital». Permiso *Acceso total* y
   *Enviar como* para la cuenta de servicio del punto 2 y para los dos equipos.
   El detalle está en [`docs/CASILLA.md`](../docs/CASILLA.md).
2. **Una cuenta de servicio con licencia M365** (por ejemplo
   `svc-tickets-ec@adium.com.uy`). Es la dueña de las conexiones de los flujos.
   Si los flujos quedan a nombre de una persona, dejan de andar el día que esa
   persona se va de la empresa.
3. **Un sitio de SharePoint** «Tickets EC» con permisos de **edición** para la
   cuenta de servicio, Excelencia Comercial y Digital, y **lectura** para el
   resto de Adium, que necesita leer para ver sus propios tickets desde el
   portal. Ver *Permisos* más abajo.
4. Para el tablero diario: una **app de Entra ID con `Sites.Selected`** de
   sólo lectura sobre ese sitio, para `exportar_powerbi.py --origen
   sharepoint`. Alternativa sin app registrada: el flujo 6 exporta las listas
   a Excel, como se explica en `FLUJOS.md`.

## Pasos, en orden

| # | Paso | Dónde | Tiempo |
|---|---|---|---|
| 1 | Crear las 10 listas con sus columnas, opciones, índices y catálogos | `sharepoint/Provisionar-Listas.ps1` (PnP PowerShell) | 10 min |
| 2 | Cargar el equipo en la lista **Personas**: rol `analista` o `coordinador`, Área = `Excelencia Comercial` o `Digital` | SharePoint | 10 min |
| 3 | Crear los 6 flujos | [`FLUJOS.md`](FLUJOS.md) | 2-3 h |
| 4 | Armar la app y pegar las fórmulas | [`APP.md`](APP.md) + `app/Formulas.fx` | 1 día |
| 5 | Publicar la app y compartirla con «Todos en Adium» (usuario, no copropietario) | Power Apps | 5 min |
| 6 | Programar el export diario y publicar el tablero | `scripts/exportar_powerbi.bat` + `powerbi/` | 30 min |
| 7 | Prueba de punta a punta: un correo real → ticket → resolver → encuesta → tablero | — | 30 min |

```powershell
# Paso 1, desde una PC con PowerShell 7:
Install-Module PnP.PowerShell -Scope CurrentUser
./powerapps/sharepoint/Provisionar-Listas.ps1 -Sitio https://<tenant>.sharepoint.com/sites/TicketsEC -ClientId <guid-de-la-app-PnP>
```

## Una sola definición

Las columnas, las opciones de cada lista (tipos, subtipos, estados, áreas,
países, unidades de negocio, áreas terapéuticas), la matriz de SLA, las
palabras del clasificador, los mercados de HQ con su ATC y las fórmulas de la
app (`app/Formulas.fx`) **se generan** desde `tickets_ec/catalogos.py`:

```bash
python scripts/generar_powerplatform.py
```

Si se agrega un tipo de ticket, se agrega en `catalogos.py` y se regenera. Un
test avisa cuando lo commiteado quedó desactualizado. En SharePoint, la opción
nueva se suma a mano en la columna, o se vuelve a correr el script: crea lo que
falta y no toca lo que ya existe.

## Permisos: lo que cada uno ve

SharePoint no filtra por fila de forma nativa. Hay dos maneras de resolverlo, y
la decisión es de IT:

- **Simple (recomendada para empezar):** todo Adium tiene lectura sobre la
  lista Tickets y la app muestra a cada uno sólo lo suyo (`SolicitanteMail =
  Yo`). Cualquiera que entre a la lista por SharePoint ve todos los tickets.
  Sirve si los pedidos no traen datos sensibles: de por sí, los pedidos a BI
  no deberían traer datos de pacientes.
- **Estricta:** el flujo 1 corta la herencia de permisos de cada ticket y le da
  lectura sólo al solicitante y a los dos equipos, con la acción *Detener la
  herencia de permisos* y *Conceder acceso a un elemento*. Tiene más costo en
  listas grandes: SharePoint recomienda menos de 50.000 elementos con permisos
  únicos.

## Límites que hay que conocer

- **Delegación:** las fórmulas de `APP.md` usan sólo filtros delegables sobre
  SharePoint (`=` en texto y en opción, `And`/`Or`, orden por fecha). Si alguien
  agrega un `in` o un `Search()` sobre Tickets, Power Apps trae sólo las
  primeras 2.000 filas y lo avisa con un subrayado azul.
- **5.000 elementos:** las columnas por las que se filtra están indexadas
  (`INDEXADAS` en `tickets_ec/sharepoint.py`).
- **Adjuntos:** el correo trae sus adjuntos al ticket con el flujo 1. Desde el
  portal se adjunta con el control de adjuntos del formulario.
- **Las horas hábiles exactas** (con el reloj detenido en espera) las calcula
  el export diario para Power BI. La app muestra un «vence» aproximado
  (`VenceEn`, días hábiles con feriados) para el semáforo de la bandeja.

## Estado de esta guía

El esquema, el script de PnP, los catálogos y las fórmulas con nombre se generan
y se prueban en este repo. Los flujos y las pantallas están escritos con los
nombres reales de los conectores y las funciones, pero **todavía no se armaron
en el tenant de Adium**. Cada paso de `FLUJOS.md` y `APP.md` tiene su prueba al
lado. Hasta pasar la prueba del paso 7, tomalos como **· REVISAR**.
