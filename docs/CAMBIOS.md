# Historial de versiones

Cada cambio que llega a `main` suma acá su entrada (la versión de arriba es la de `tickets_ec.__version__`) y
regenera la documentación del proyecto con `python scripts/documentar.py`. Un test avisa si una de las dos cosas
quedó vieja.

## 1.2.1 · 2026-11-05 · Arreglos de Inicio y Bandeja

- «Abrir» en Inicio y elegir una fila de la Bandeja rompían con `StreamlitWidgetAlreadyInstantiatedError`: la
  página se cambiaba después de dibujar el selector de la barra lateral. Ahora se pide para la próxima corrida y
  se aplica antes de dibujarlo.
- La Bandeja con el filtro «Estado» vacío y una búsqueda rompía con `KeyError: 'Creado'`. Un filtro vacío ahora
  es «todos» (como los demás) y la búsqueda ya no se queda sin columnas cuando no hay filas.
- Pruebas nuevas que recorren la app de verdad en modo local (`tests/test_app_local.py`): Abrir desde Inicio, la
  Bandeja con Estado vacío y una búsqueda sin resultados.

## 1.2.0 · 2026-11-05 · Portal propio y FreshService

- **Portal del solicitante** (🌐 Portal), al estilo del portal de FreshService de IT: Inicio, Enviar un ticket y Mis
  tickets, con la conversación, las respuestas con adjuntos y la conformidad. Quien entra con su cuenta de Adium y
  no es del equipo ve sólo el portal, y cada uno ve únicamente lo suyo.
- **Conector con FreshService** (apagado por defecto). «Incidencia en = Excelencia Comercial» es un pedido nuestro
  que resuelve IT, así que IT suma una opción propia («Reportería Excelencia Comercial»). Lo que entra por ahí
  llega a la mesa, y el estado y la resolución vuelven a FreshService. El texto del pedido a IT está en
  `docs/PORTAL.md`.
- **Documentación del proyecto que se regenera con cada versión** (`docs/PROYECTO.md` y `docs/PROYECTO.html`, para
  presentar).
- Ayuda por tipo de pedido en el portal (`catalogos.AYUDA`) y canal «FreshService».

## 1.1.0 · 2026-10-21 · Modo compartido

- Cada integrante del equipo, en su PC (sola o dentro de la suite Adium All in One), entra con su cuenta de
  Microsoft de Adium y trabaja sobre las mismas listas de SharePoint, que alimenta la casilla.
- Escrituras con eTag: si dos personas tocan el mismo ticket, la segunda recibe «otro integrante lo cambió» y nada
  se pisa. Hay una cola para cuando se corta la red y un candado para que el mismo correo no abra dos tickets.
- Roles desde la lista Personas. Encuesta de conformidad contestada por correo. `config.equipo.toml` sin secretos.
- El `.bat` ya no se abre y se cierra: consigue Python, instala lo que falta y dice qué falló.

## 1.0.0 · 2026-10-21 · La mesa

- Casilla de correo → ticket con solicitante, área, país, tipo, subtipo, prioridad, ATC, área terapéutica, unidad
  de negocio y equipo resolutor (Excelencia Comercial o Digital), clasificados automáticamente.
- Estados con fecha y hora, subestados, SLA en horas hábiles con el reloj detenido mientras se espera al
  solicitante, y encuesta de conformidad con cierre tácito.
- Tablero de Power BI de 8 páginas, con cada KPI verificado contra la app; `.pbit`, PBIP para Fabric y publicación
  por API.
- Paquete de Power Platform (listas de SharePoint, flujos, app de Power Apps) generado desde los mismos catálogos,
  y la guía paso a paso dentro de la app y de la suite.
