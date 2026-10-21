# Indicadores de la mesa

Cada indicador tiene **una** definición, escrita dos veces a propósito: en
Python (`tickets_ec/indicadores.py`, la que muestra la app) y en DAX
(`powerbi/medidas.py`, la del tablero). `powerbi/armar_tablero.py` evalúa cada
medida DAX sobre los datos del `.pbit` y la compara con Python: en total, mes
por mes y por equipo resolutor. Si no dan igual, el tablero no se entrega.
Resultado de la última corrida: [`powerbi/VERIFICACION.md`](../powerbi/VERIFICACION.md).

## Cómo se mide el tiempo

- **Horas hábiles**, de 9 a 18, de lunes a viernes, sin los feriados de
  Uruguay (configurables).
- **El reloj se detiene** mientras el ticket espera al solicitante: está «En
  espera del solicitante» o «Resuelto» esperando la conformidad. Si se pidió
  un dato y tardaron tres días en mandarlo, esos días no son del equipo.
- **SLA por tipo de ticket y prioridad**, en días hábiles:

| Tipo de ticket | Crítica | Alta | Media | Baja | Equipo |
|---|---|---|---|---|---|
| Incidente / dato incorrecto | 1 | 2 | 3 | 5 | Excelencia Comercial |
| Solicitud de permisos | 1 | 1 | 2 | 3 | Excelencia Comercial |
| Nuevo desarrollo | 5 | 10 | 20 | 30 | Excelencia Comercial |
| Cambio en tablero existente | 2 | 5 | 8 | 15 | Excelencia Comercial |
| Pedido de información | 1 | 3 | 5 | 10 | Excelencia Comercial |
| Pedido digital | 1 | 3 | 5 | 10 | Digital |
| Capacitación / consulta | 1 | 3 | 5 | 10 | Excelencia Comercial |

La primera respuesta tiene su propio plazo, según la prioridad: 2, 4, 9 y 18
horas hábiles. Los dos plazos son una **propuesta inicial**. Se cambian en
`tickets_ec/catalogos.py` después de correr la mesa un trimestre.

## El período

Un ticket es del mes en que **entró**. Hay dos excepciones:
- **Resueltos** cuenta por fecha de resolución;
- **Backlog** es una foto al último día del período.

Así se compara lo que entró con lo que salió.

## Los indicadores

| Indicador | Definición | Lectura |
|---|---|---|
| Tickets recibidos | Pedidos creados en el período | Demanda |
| Tickets resueltos | Pedidos resueltos en el período, entren cuando entren | Capacidad |
| Backlog fin de período | Entraron hasta el último día del período y todavía no estaban resueltos ni cancelados | Si crece mes a mes, la demanda le gana a la capacidad |
| Pendientes del equipo | Hoy en Nuevo, Asignado, En curso o Reabierto | Carga actual |
| Vencidos sin resolver | Pendientes que ya pasaron su SLA | Alerta |
| % en SLA | De los resueltos, cuántos en plazo | Meta ≥ 85 % |
| % respuesta en SLA | Primera respuesta en plazo | Que nadie quede sin respuesta |
| Horas a la primera respuesta | Promedio, en horas hábiles | — |
| Días de resolución | Promedio y mediana, en días hábiles efectivos | La mediana no la mueven los pocos larguísimos |
| Tasa de reapertura | Resueltos que el solicitante devolvió al menos una vez | Calidad de la primera entrega |
| % sin idas y vueltas | Resueltos sin pedir datos ni reaperturas | Calidad del pedido y de la respuesta |
| % de respuesta a la encuesta | Respondidas sobre encuestas cerradas (respondidas + tácitas) | Si es baja, la conformidad dice poco |
| % conformidad | Conformes sobre respondidas | Meta ≥ 85 % |
| % conformidad con tácita | Conformes + tácitas sobre encuestas cerradas | El silencio cuenta como conforme |
| Satisfacción (1 a 5) | Promedio de la nota | — |
| % satisfechos (4 y 5) | Notas de 4 o 5 sobre las notas | — |
| **Índice de efectividad** | 40 % · % en SLA + 40 % · % conformidad con tácita + 20 % · (1 − reapertura) | Un solo número para el comité. Meta ≥ 85 % |

**Semáforo del área:** verde ≥ 85 %, ámbar entre 70 y 84 %, rojo < 70 %.

## Por qué se abre

- **Quién pide:** el solicitante, el área solicitante y el país. Salen del
  directorio (`datos/directorio.csv` o la lista Personas), nunca del texto.
- **Qué pide:** el tipo de ticket y el subtipo. Las categorías son nuevo
  desarrollo, pedido de información, solicitud de permisos, incidente, cambio,
  pedido digital y capacitación.
- **Sobre qué:** el ATC, el área terapéutica, la unidad de negocio, el mercado
  conformado de HQ, la fuente de datos y el tablero afectado.
  - El área terapéutica sale del ATC con la regla del manual (cap. 24.1).
  - La unidad de negocio sale de la Planilla Maestra: la C10 va a
    «Gastro + Hipercol.» y la pregabalina a «Osteo Dolor».
  - Metabolismo (A08/A10) va a «Metab & Obesidad Lic». Si el producto es
    propio, se pasa a mano a «Pr».
- **Quién resuelve:** el equipo resolutor (Excelencia Comercial o Digital) y el
  analista.
