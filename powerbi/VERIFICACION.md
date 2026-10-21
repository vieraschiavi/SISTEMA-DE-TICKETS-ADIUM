# Verificación del tablero · 2026-10-21 13:01

Origen: demo (semilla 42, hasta 2026-10-21 12:00:00)
Archivo: `Tickets_Excelencia_Comercial_y_Digital.pbit` · 5 tablas · 3 relaciones · 44 medidas · 9 páginas

## Veredicto: LISTO

- Gate del archivo (`dxl.verificacion`): listo (0 faltas, 1 avisos)
- Gate del proyecto PBIP (Fabric / Git): listo (0 faltas, 1 avisos) · `Tickets_Excelencia_Comercial_y_Digital_PBIP.zip`
- Tipos de columna iguales a los datos: sí (1 corregidas sobre la inferencia por muestra)
- Números: 220/220 medidas iguales a `tickets_ec.indicadores` (total, 7 meses y cada equipo resolutor)
- Medidas rechazadas por el catálogo: 0
- Páginas: 8/8
- Segmentadores con un solo valor: 0

## Tipos corregidos

- Tickets[Días abierto]: string → double

## Arreglos automáticos del modelo

- Tickets[Fecha]: oculta (clave de relación)
- Estados[Número]: oculta (clave de relación)
- Encuestas[Número]: oculta (clave de relación)
- [Tickets[Orden prioridad]]: formato → #,0
- [Tickets[Orden estado]]: formato → #,0
- [Tickets[Fecha creación]]: formato → dd/mm/yyyy
- [Tickets[Fecha asignación]]: formato → dd/mm/yyyy
- [Tickets[Fecha primera respuesta]]: formato → dd/mm/yyyy
- [Tickets[Fecha resolución]]: formato → dd/mm/yyyy
- [Tickets[Fecha resolución día]]: formato → dd/mm/yyyy
- [Tickets[Fecha cierre]]: formato → dd/mm/yyyy
- [Tickets[Fecha cancelación]]: formato → dd/mm/yyyy
- [Tickets[Fecha salida backlog]]: formato → dd/mm/yyyy
- [Tickets[Horas primera respuesta]]: formato → #,0.00
- [Tickets[Respuesta en SLA]]: formato → #,0
- [Tickets[Horas resolución]]: formato → #,0.00
- [Tickets[Días resolución]]: formato → #,0.00
- [Tickets[SLA horas]]: formato → #,0
- [Tickets[SLA días]]: formato → #,0
- [Tickets[En SLA]]: formato → #,0
- [Tickets[Horas en espera]]: formato → #,0.00
- [Tickets[Resuelto]]: formato → #,0
- [Tickets[Cancelado]]: formato → #,0
- [Tickets[Pendiente equipo]]: formato → #,0
- [Tickets[Vencido]]: formato → #,0
- [Tickets[Reaperturas]]: formato → #,0
- [Tickets[Veces en espera]]: formato → #,0
- [Tickets[Primer contacto]]: formato → #,0
- [Tickets[CSAT]]: formato → #,0
- [Estados[Orden estado]]: formato → #,0
- [Estados[Fecha cambio]]: formato → dd/mm/yyyy
- [Estados[Horas en estado]]: formato → #,0.00
- [Encuestas[Ronda]]: formato → #,0
- [Encuestas[Fecha envío]]: formato → dd/mm/yyyy
- [Encuestas[Fecha respuesta]]: formato → dd/mm/yyyy
- [Encuestas[CSAT]]: formato → #,0
- [Encuestas[Respondida]]: formato → #,0
- [Encuestas[Horas para responder]]: formato → #,0.00
- [Calendario[Año]]: formato → 0
- [Calendario[Mes orden]]: formato → 0
- [Calendario[Día hábil]]: formato → #,0
- Tickets[Mail solicitante] oculto; se muestra «Mail solicitante (enmascarado)», enmascarado en Power Query

## Ítems del gate que no dieron OK

- aviso · ¿Abre solo?: 4 tablas leen de afuera (Calendario · Encuestas · Estados · Tickets) y 0 llevan los datos adentro. Las de afuera necesitan que el origen esté disponible en la máquina que abre el archivo.

## KPIs del total (los mismos que muestra el tablero)

| KPI | Valor |
|---|---|
| Tickets recibidos | 1614 |
| Tickets resueltos | 1516 |
| Backlog fin de período | 32 |
| Pendientes del equipo | 31 |
| Vencidos sin resolver | 2 |
| Cancelados | 66 |
| Solicitantes | 90 |
| Áreas que piden | 12 |
| % en SLA | 76.4% |
| % respuesta en SLA | 83.4% |
| Horas primera respuesta | 3.93 |
| Días de resolución | 4.13 |
| Días de resolución (mediana) | 2.83 |
| Tasa de reapertura | 9.3% |
| % sin idas y vueltas | 70.4% |
| Encuestas enviadas | 1691 |
| % de respuesta a la encuesta | 66.3% |
| % conformidad | 84.2% |
| % conformidad con tácita | 89.6% |
| Satisfacción (1 a 5) | 3.97 |
| % satisfechos (4 y 5) | 72.2% |
| Índice de efectividad | 84.5% |
