# CLAUDE.md — Tickets · Excelencia Comercial & Digital

Mesa de pedidos por correo de Excelencia Comercial y Digital (Adium), con
tablero de Power BI y paquete de Power Platform. Leé `README.md` primero.

## Comandos

| Objetivo | Comando |
|---|---|
| Linter | `ruff check .` |
| Tests | `python -m pytest -q tests` |
| Demo | `python -m tickets_ec.demo` (no pisa una base existente) |
| App | `streamlit run app/app.py` |
| E2E en Chromium | `python scripts/e2e_ui.py [carpeta-capturas]` |
| Tablero (necesita `../Power-bi` o `ADIUM_SUITE`) | `python powerbi/armar_tablero.py` |
| Regenerar Power Platform | `python scripts/generar_powerplatform.py` |

## Reglas

- **Una sola definición.** Estados, tipos, SLA, áreas y unidades de negocio
  viven en `tickets_ec/catalogos.py`. Power Platform se regenera desde ahí, y
  un test avisa si quedó viejo.
- **Todo cambio de un ticket pasa por `servicio.Mesa`.** Ni la app ni los
  scripts tocan la base directo.
- **Ningún KPI sin verificar.** Una medida DAX nueva lleva `kpi` en
  `powerbi/medidas.py` y su equivalente en `indicadores.kpis`. El build las
  compara y no entrega si difieren.
- **El analizador del motor no acusa al generador.** Si una medida dispara una
  regla R01-R26, se corrige la medida, no la regla.
- **Conectores apagados por defecto.** El envío de correo sale apagado y los
  secretos van sólo por entorno (`TICKETS_*`).
- **Demo sintética.** Nada de personas ni correos reales.
- Español rioplatense en textos, comentarios y commits.
