"""
Los indicadores de efectividad de la mesa, con UNA definición.

Cada KPI está escrito dos veces a propósito: acá en Python (la app lo
muestra y el test lo prueba) y en DAX en `powerbi/medidas.py` (lo muestra el
tablero). `powerbi/armar_tablero.py` evalúa cada medida DAX sobre los datos
del .pbit y la compara con este módulo, total y mes por mes: si las dos
definiciones se separan, el tablero no se entrega. Es la regla de la casa
—ningún KPI sin verificar su número contra el origen— aplicada a una mesa
de tickets.

Período: un ticket «es del mes» en que ENTRÓ (fecha de creación), salvo
«Resueltos», que cuenta por fecha de resolución, y «Backlog», que es una
foto al último día del período. Así «Recibidos» y «Resueltos» de un mes se
pueden comparar (entró más de lo que salió → crece el backlog).
"""
from __future__ import annotations

from datetime import date
from statistics import median

from . import catalogos as C

#: Semáforo del área (≥ 85 % verde, 70-84 % ámbar, < 70 % rojo).
VERDE, AMBAR = 0.85, 0.70
#: Pesos del índice de efectividad: cumplir el plazo, que el pedido quede
#: bien y que no vuelva. Suman 1.
PESO_SLA, PESO_CONFORMIDAD, PESO_SIN_REAPERTURA = 0.4, 0.4, 0.2


def semaforo(valor: float | None) -> str:
    if valor is None:
        return "Sin dato"
    return "Verde" if valor >= VERDE else "Ámbar" if valor >= AMBAR else "Rojo"


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def _prom(valores) -> float | None:
    v = [x for x in valores if x is not None]
    return sum(v) / len(v) if v else None


def kpis(tickets: list[dict], encuestas: list[dict], desde: date | None = None, hasta: date | None = None,
         todos: list[dict] | None = None) -> dict:
    """Los KPIs del período [desde, hasta] (por fecha de creación).

    `tickets` ya viene filtrado por lo demás (área, analista, tipo…);
    `todos` son esos mismos tickets SIN el filtro de fechas, para contar los
    resueltos por fecha de resolución y el backlog a fin de período.
    """
    todos = tickets if todos is None else todos

    def en_periodo(d):
        return d is not None and (desde is None or d >= desde) and (hasta is None or d <= hasta)

    t = [x for x in tickets if en_periodo(x["Fecha"])]
    numeros = {x["Número"] for x in t}
    enc = [e for e in encuestas if e["Número"] in numeros]
    resueltos_t = [x for x in t if x["Resuelto"] == 1]
    conformes = sum(e["Resultado"] == C.CONFORME for e in enc)
    no_conformes = sum(e["Resultado"] == C.NO_CONFORME for e in enc)
    tacitas = sum(e["Resultado"] == C.TACITA for e in enc)
    cerradas = conformes + no_conformes + tacitas
    csats = [e["CSAT"] for e in enc if e["CSAT"] is not None]
    fin = hasta or max((x["Fecha"] for x in todos), default=None)

    k = {
        "Tickets recibidos": len(t),
        "Tickets resueltos": sum(1 for x in todos if x["Fecha resolución día"] is not None
                                 and en_periodo(x["Fecha resolución día"])),
        "Backlog fin de período": (sum(1 for x in todos if x["Fecha"] <= fin and (
            x["Fecha salida backlog"] is None or x["Fecha salida backlog"] > fin)) if fin else 0),
        "Pendientes del equipo": sum(x["Pendiente equipo"] for x in t),
        "Vencidos sin resolver": sum(x["Vencido"] for x in t),
        "Cancelados": sum(x["Cancelado"] for x in t),
        "Solicitantes": len({x["Mail solicitante"] for x in t}),
        "Áreas que piden": len({x["Área solicitante"] for x in t}),
        "% en SLA": _prom(x["En SLA"] for x in t),
        "% respuesta en SLA": _prom(x["Respuesta en SLA"] for x in t),
        "Horas primera respuesta": _prom(x["Horas primera respuesta"] for x in t),
        "Días de resolución": _prom(x["Días resolución"] for x in t),
        "Días de resolución (mediana)": (median([x["Días resolución"] for x in t if x["Días resolución"] is not None])
                                         if any(x["Días resolución"] is not None for x in t) else None),
        "Tasa de reapertura": _div(sum(1 for x in resueltos_t if x["Reaperturas"] > 0), len(resueltos_t)),
        "% sin idas y vueltas": _prom(x["Primer contacto"] for x in t),
        "Encuestas enviadas": len(enc),
        "% de respuesta a la encuesta": _div(conformes + no_conformes, cerradas),
        "% conformidad": _div(conformes, conformes + no_conformes),
        "% conformidad con tácita": _div(conformes + tacitas, cerradas),
        "Satisfacción (1 a 5)": _prom(csats),
        "% satisfechos (4 y 5)": _div(sum(c >= 4 for c in csats), len(csats)),
    }
    sla, conf, reap = k["% en SLA"], k["% conformidad con tácita"], k["Tasa de reapertura"]
    k["Índice de efectividad"] = (PESO_SLA * sla + PESO_CONFORMIDAD * conf + PESO_SIN_REAPERTURA * (1 - reap)
                                  if None not in (sla, conf, reap) else None)
    return k


def por(tickets: list[dict], encuestas: list[dict], columna: str, **kw) -> list[dict]:
    """Los KPIs abiertos por una columna de Tickets (Área solicitante, Analista, Tipo de ticket…)."""
    valores = sorted({x[columna] for x in tickets}, key=str)
    filas = []
    for v in valores:
        sub = [x for x in tickets if x[columna] == v]
        filas.append({columna: v, **kpis(sub, encuestas, todos=sub, **kw)})
    return filas


def mensual(tickets: list[dict], encuestas: list[dict], calendario: list[dict]) -> list[dict]:
    """Un renglón por mes del calendario."""
    meses: dict[str, list[date]] = {}
    for d in calendario:
        meses.setdefault(d["Período"], []).append(d["Fecha"])
    return [{"Período": m, **kpis(tickets, encuestas, min(f), max(f))} for m, f in meses.items()]
