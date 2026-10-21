# La casilla corporativa de tickets

La casilla la crea **IT de Adium**: es un buzón compartido de Exchange Online.
Este repo no la crea ni puede crearla. Lo que sí trae es el pedido listo para
mandar y las tres formas de conectarla.

## El pedido a IT (para copiar y pegar)

> **Asunto:** Alta de buzón compartido «Tickets · Excelencia Comercial & Digital»
>
> Hola. Para centralizar los pedidos que reciben Excelencia Comercial y Digital
> (tableros, información de mercado, permisos de Power BI, pedidos digitales)
> necesitamos:
>
> 1. **Buzón compartido** `tickets.excelenciacomercial@adium.com.uy`, nombre
>    visible «Tickets · Excelencia Comercial & Digital».
> 2. **Acceso total** y **Enviar como** para los integrantes de Excelencia
>    Comercial y de Digital, y para la cuenta de servicio del punto 3.
> 3. **Una cuenta de servicio con licencia M365** (`svc-tickets-ec`), dueña de
>    los flujos de Power Automate, para que no dependan de una persona.
> 4. **Un sitio de SharePoint** «Tickets EC», con edición para los dos equipos
>    y la cuenta de servicio, y lectura para Adium.
> 5. (Opcional, para el tablero diario sin intervención) **Una app de Entra
>    ID** con permiso de aplicación `Sites.Selected` (sólo lectura) sobre ese
>    sitio. Si además se usa la app de Python con Graph: `Mail.ReadWrite` y
>    `Mail.Send`, acotados a ESE buzón con una *Application Access Policy*
>    (`New-ApplicationAccessPolicy -AccessRight RestrictAccess`).
>
> Gracias.

## Tres formas de conectarla

| Camino | Necesita de IT | Cuándo |
|---|---|---|
| **Power Platform** (recomendado) | puntos 1 a 4 | Entorno corporativo: los flujos de `powerapps/FLUJOS.md` leen el buzón y escriben en SharePoint |
| **Power Automate → carpeta + app de Python** | puntos 1 y 3 | Un flujo de dos pasos deja cada correo como `.eml` en una carpeta sincronizada; `scripts/procesar_casilla.py` lo procesa con `fuente = "carpeta"` |
| **Microsoft Graph + app de Python** | puntos 1 y 5 | La app lee y manda directo (`fuente = "graph"`, `envio = "graph"`) |

IMAP con usuario y contraseña **no funciona** en Exchange Online, porque
Microsoft apagó la autenticación básica. `FuenteIMAP` acepta un token
OAuth (XOAUTH2) para otros servidores.

### El flujo de dos pasos (camino del medio)

1. *Cuando llega un nuevo correo electrónico a un buzón compartido (V2)*, con el buzón de la mesa y la carpeta Inbox.
2. *Exportar correo electrónico (V2)* (*Export email*) con el `Id del mensaje` del disparador.
3. *Crear archivo* (OneDrive para la Empresa o SharePoint) en `Tickets EC/entrada/`,
   con el nombre `@{triggerOutputs()?['body/id']}.eml` y el contenido del paso 2.

En la PC del equipo, esa carpeta sincronizada va como `carpeta_entrada` en
`config.toml`, y el Programador de tareas corre `scripts\procesar_casilla.bat`
cada 5 minutos. Los procesados se mueven a `entrada/procesados/`.

## Lo que la mesa hace con cada correo

- **Responde con un acuse** que lleva el número en el asunto: `[EC-00042]`.
  Toda respuesta a ese hilo vuelve al mismo ticket, aunque el cliente de
  correo pierda las cabeceras.
- **Ignora los automáticos** (fuera de la oficina, rebotes, `Auto-Submitted`)
  y lo que manda la propia casilla. Sin esto, dos respuestas automáticas
  abren tickets sin fin.
- **No duplica**: un `Message-ID` ya visto no vuelve a entrar.
- **Si el solicitante responde un pedido que estaba en espera**, lo devuelve a
  «En curso» y el reloj del SLA vuelve a correr.
- **Si responde un ticket cerrado**, abre uno nuevo que dice de cuál viene.
- **Los correos que manda llevan `Auto-Submitted: auto-generated`**, para que
  el «fuera de la oficina» del otro lado no conteste.
- **Envío apagado por defecto.** Hasta poner `envio_activo = true`, cada
  correo queda como `.eml` en `datos/salida/` y nada sale de la máquina.
