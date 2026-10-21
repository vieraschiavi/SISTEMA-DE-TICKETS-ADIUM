# La mesa en las PCs de todo el equipo

Seis personas con la suite Adium All in One (o con «Abrir Tickets EC.bat»), cada una en su PC, trabajando
**la misma mesa**: lo que entra a la casilla lo ven todos, el que toma un ticket queda como dueño para los
demás, y lo que resuelve uno cuenta en los indicadores de todos. Cada uno entra con su **cuenta de
Microsoft de Adium** (el mail y la contraseña corporativos, con el MFA de siempre).

> **· REVISAR** — el modo compartido está probado contra un doble de SharePoint (`tests/test_compartida.py`:
> dos PCs, choques, el mismo correo leído dos veces, la red que se corta), no contra el tenant de Adium. Deja
> de estar en revisión cuando pasa la prueba del final de esta página con dos cuentas reales.

## Cómo queda armado

```
                 ┌──────────────────────────────┐
  correo  ─────▶ │  Casilla compartida (M365)   │
                 └──────────────┬───────────────┘
                                │ la lee cada PC con la cuenta de quien la usa;
                                │ la primera que reclama un correo se lo queda
                                ▼
                 ┌──────────────────────────────┐
                 │  Listas de SharePoint        │  ◀── Power Apps y los flujos (opcionales)
                 │  Tickets · Eventos ·         │  ──▶ Power BI (export diario)
                 │  Encuestas · Personas ·      │
                 │  Correos                     │
                 └──────────────┬───────────────┘
            ┌───────────┬───────┴───┬───────────┐
            ▼           ▼           ▼           ▼
         PC Ana      PC Eli      PC Juan     … (cada una con su copia local)
```

**La base es SharePoint, no una PC.** Cada PC tiene una copia local (SQLite) para que la bandeja, los
indicadores y el export a Power BI anden rápido. Cada `segundos_sync` (60 por defecto) trae lo que cambiaron
los demás y lee la casilla. Si no hay nadie con la app abierta, los correos esperan en la casilla y entran
cuando alguien la abre.

**Por qué no alcanza con la casilla sola.** La casilla trae los pedidos, pero no sabe quién tomó cada uno, en
qué estado está ni qué contestó el solicitante en la encuesta. Ese estado tiene que vivir en un lugar que
todos lean y escriban: las listas de SharePoint, que el área ya tiene con Microsoft 365 y que son las mismas
que usan Power Apps y el tablero.

**Por qué no una carpeta compartida con la base.** Un SQLite en OneDrive o en una carpeta de red con seis
personas escribiendo se corrompe: OneDrive sincroniza el archivo entero y gana el último que guardó.

## Lo que evita que dos personas se pisen

| Situación | Qué pasa |
|---|---|
| Ana y Eli tocan «Tomarlo» en el mismo ticket a la vez | Cada escritura va con la versión que esa PC leyó (`If-Match` con el eTag). La segunda recibe «Otro integrante cambió este ticket mientras lo tenías abierto»: su pantalla trae la versión nueva y nada se pisa |
| Dos PCs leen el mismo correo de la casilla | Antes de procesarlo, cada una crea su ítem en la lista **Correos** con el Message-ID, que tiene valores únicos. La primera gana; la segunda lo saltea. Un solo ticket |
| Se corta la red a la mitad | Los eventos (comentarios, cambios de estado, avisos) quedan en una cola de la PC y suben en la próxima sincronización, sin duplicarse. La barra lateral muestra «⏳ N cambios esperando red» |
| El número del ticket | `EC-00042` sale del id del ítem de la lista, igual que en el flujo 1 de Power Automate: no hay dos PCs que puedan dar el mismo número |
| El correo de un acuse no sale | El ticket queda igual (ya está en la lista) y el `.eml` en `datos/salida/`. La barra lateral avisa cuántos no salieron |

## Quién puede qué

Sale de la lista **Personas** (columna Rol). La carga un coordinador desde ⚙️ Configuración o directo en
SharePoint.

| Rol | Puede |
|---|---|
| **coordinador** | Todo: asignar a otro, reasignar, dar de alta y de baja integrantes |
| **analista** | Tomar lo sin asignar, trabajar y resolver lo suyo, dejar notas en cualquiera, leer la casilla |
| cualquier otra cuenta de Adium | No entra a la app: escribe a la casilla |

Los permisos de la app ordenan el trabajo; lo que de verdad impide escribir es el permiso del sitio de
SharePoint (edición sólo para los dos equipos y la cuenta de servicio).

## La contraseña: quién la ve

**Nadie de la app.** «🔑 Ingresar con mi cuenta de Adium» abre la página de inicio de sesión de Microsoft en el
navegador —la misma de Outlook y Teams, con el MFA—. Microsoft le devuelve a la app un token de esa persona,
que vive en memoria mientras la app está abierta: no se guarda en disco y no viaja en el paquete. Lo hace
MSAL, la biblioteca oficial de Microsoft.

## Qué hay que pedirle a IT (una vez)

1. **El buzón y el sitio** (paso 1 de la guía): la casilla con *Acceso total* para los dos equipos y *Enviar
   como* para mandar desde ella; el sitio «Tickets EC» con edición para los dos equipos.
2. **La app de Entra ID «Tickets EC»**, en *Registros de aplicaciones*:
   - Tipo de cuenta: *sólo este directorio* (Adium).
   - Plataforma *Aplicaciones móviles y de escritorio*, URI de redirección `http://localhost`.
   - *Permitir flujos de cliente público*: **Sí**. Sin secreto ni certificado.
   - Permisos **delegados** de Microsoft Graph: `Sites.ReadWrite.All`, `Mail.ReadWrite.Shared`,
     `Mail.Send.Shared` (y `User.Read`, que viene por defecto), con **consentimiento de administrador**.
   - Que pasen el *id de directorio (tenant)* y el *id de aplicación (cliente)*.

   Son permisos delegados: cada persona puede, con la app, exactamente lo que su cuenta ya puede en el sitio y
   en la casilla. Si IT prefiere no dar `Sites.ReadWrite.All` en todo el tenant, la alternativa es
   `Sites.Selected` delegado sobre el sitio de la mesa.

## Ponerlo en marcha

1. Crear las listas con `powerapps/sharepoint/Provisionar-Listas.ps1` (paso 2 de la guía). El script crea
   también la lista **Correos** con el Title único, y los índices de `Modified` que usa la sincronización.
2. Cargar a los integrantes en **Personas** con su rol (paso 3).
3. El coordinador copia `config.equipo.ejemplo.toml` a **`config.equipo.toml`** en la carpeta de la mesa y
   completa `entra_tenant`, `entra_cliente` y `sharepoint_host`. No tiene secretos (la app los rechaza), así
   que puede viajar en el paquete de la suite o commitearse en el repo privado.
4. Cada integrante abre la suite (pestaña de la mesa) o «Abrir Tickets EC.bat», toca **Ingresar con mi cuenta
   de Adium** y listo. El `.bat` instala `msal` si falta.
5. Cuando IT confirme *Enviar como*, poner `envio_activo = true` en `config.equipo.toml`. Hasta entonces los
   correos de la mesa quedan como `.eml` en cada PC y no le llegan a nadie (es el apagado por defecto).

## La encuesta de conformidad, sin servidor

En modo local, el correo de «resuelto» trae un link a la página de la encuesta. En modo compartido no hay una
app central que el solicitante pueda abrir, así que los dos botones arman **un correo a la casilla**
(«[EC-00042] Conforme» / «[EC-00042] No conforme»). La PC que lo lee cierra o reabre el ticket. En la primera
línea el solicitante puede poner del 1 al 5 qué tan satisfecho quedó; el resto es el comentario. Responder el
correo con «Conforme» en el asunto hace lo mismo.

## Límites que hay que conocer

- **Nadie tiene que leer la casilla desde Outlook.** La app toma los correos *no leídos*: uno que alguien abre
  en Outlook antes de que una PC lo procese queda marcado como leído y no entra. Se atiende desde la app.
- Si nadie tiene la app abierta, los correos esperan. Para que entren igual (y salga el acuse al instante),
  el flujo 1 de Power Automate puede seguir corriendo: escribe en las mismas listas y con el mismo número.
- La primera vez cada PC trae las listas enteras; después, sólo lo cambiado desde la última vez.
- Dos detalles de SharePoint que hay que confirmar en el tenant: que un Title repetido en Correos responda
  409 (la app lo trata así, y también un 400 que diga «duplicado») y que el índice de `Modified` quede creado.

## Prueba antes de repartirlo

Con dos cuentas reales del equipo, en dos PCs:

1. Mandar un correo a la casilla desde una tercera cuenta: aparece en las dos PCs con el mismo número.
2. Los dos tocan «Tomarlo» casi a la vez: uno lo toma y el otro ve el aviso de que otro lo cambió.
3. El dueño lo resuelve; la tercera cuenta toca «Sí, conforme» en el correo: el ticket queda cerrado en
   las dos PCs.
4. Desconectar la red de una PC, dejar una nota, reconectar: la nota aparece en la otra.
