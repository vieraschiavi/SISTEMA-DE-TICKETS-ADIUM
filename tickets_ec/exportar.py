"""
El modelo estrella que lee Power BI: cuatro tablas, una fila = un hecho.

* **Tickets** — una fila por ticket, con TODO lo que un tablero necesita ya
  calculado en horas hábiles: el reloj detenido, el SLA de su tipo y
  prioridad, si vence, cuánto tardó la primera respuesta. Calcular horas
  hábiles con feriados en DAX es posible y lento; acá se calcula una vez,
  con la MISMA función que usa la bandeja de la app, así el número del
  tablero y el de la pantalla no pueden diferir.
* **Estados** — una fila por cambio de estado, con las horas hábiles que el
  ticket pasó en el estado al que entró. Es el «tiempo en cada etapa».
* **Encuestas** — una fila por encuesta de conformidad enviada.
* **Calendario** — un día por fila, del primer ticket a hoy.

Las columnas tienen nombres en castellano y con espacios porque son lo que
el usuario ve en la lista de campos de Power BI.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from . import catalogos as C
from . import sla as S
from .almacen import Almacen
from .config import Config

MESES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
TRAMOS = ("0-2 días", "3-5 días", "6-10 días", "Más de 10 días")


def tramo(dias: float) -> str:
    if dias <= 2:
        return TRAMOS[0]
    if dias <= 5:
        return TRAMOS[1]
    if dias <= 10:
        return TRAMOS[2]
    return TRAMOS[3]


def _r(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(x, n)


def fila_ticket(t: dict, eventos: list[dict], nombres: dict[str, str], ahora: datetime, cfg: Config) -> dict:
    """Una fila de la tabla Tickets."""
    resuelto = t["resuelto_en"] if t["estado"] in (C.RESUELTO, C.CERRADO) else None
    fin = resuelto or t["cancelado_en"] or ahora
    efectivas = S.horas_efectivas(t["creado_en"], fin, eventos, cfg)
    sla_h = C.sla_horas(t["tipo"], t["prioridad"])
    p = C.POR_PRIORIDAD.get(t["prioridad"], C.POR_PRIORIDAD[C.PRIORIDAD_DEFECTO])
    primera = t["primera_respuesta_en"]
    horas_resp = S.horas_habiles(t["creado_en"], primera, cfg) if primera else None
    pendiente = t["estado"] in C.PENDIENTES_EQUIPO
    detenidas = S.horas_detenidas(eventos, fin, cfg)
    salida = resuelto or t["cancelado_en"]
    cancelado = t["estado"] == C.CANCELADO
    return {
        "Número": t["numero"],
        "Asunto": t["asunto"],
        "Solicitante": t["solicitante_nombre"],
        "Mail solicitante": t["solicitante_mail"],
        "Área solicitante": t["area"] or C.AREA_DEFECTO,
        "País": t["pais"] or C.PAIS_DEFECTO,
        "Tipo de ticket": t["tipo"],
        "Subtipo": t["subtipo"] or "",
        "Prioridad": t["prioridad"],
        "Orden prioridad": p.orden,
        "Canal": t["canal"],
        "ATC": t["atc"] or "Sin ATC",
        "ATC nivel 1": (t["atc"] or "")[:1] or "Sin ATC",
        "Área terapéutica": t["area_terapeutica"] or C.AREA_TERAPEUTICA_DEFECTO,
        "Unidad de negocio": t["unidad_negocio"] or C.UNIDAD_NEGOCIO_DEFECTO,
        "Mercado": t["mercado"] or "Sin mercado",
        "Fuente de datos": t["fuente_datos"] or C.FUENTE_DEFECTO,
        "Tablero": t["tablero"] or "",
        "Estado": t["estado"],
        "Orden estado": C.ORDEN_ESTADO[t["estado"]],
        "Subestado": t["subestado"] or "",
        "Equipo resolutor": t["equipo"] or C.EQUIPO_DEFECTO,
        "Analista": nombres.get(t["analista_mail"] or "", "Sin asignar"),
        "Fecha creación": t["creado_en"],
        "Fecha": t["creado_en"].date(),
        "Fecha asignación": t["asignado_en"],
        "Fecha primera respuesta": primera,
        "Fecha resolución": resuelto,
        "Fecha resolución día": resuelto.date() if resuelto else None,
        "Fecha cierre": t["cerrado_en"],
        "Fecha cancelación": t["cancelado_en"],
        "Fecha salida backlog": salida.date() if salida else None,
        "Horas primera respuesta": _r(horas_resp),
        "Respuesta en SLA": None if horas_resp is None else int(horas_resp <= p.horas_respuesta),
        "Horas resolución": _r(efectivas) if resuelto else None,
        "Días resolución": _r(efectivas / C.HORAS_DIA) if resuelto else None,
        "SLA horas": sla_h,
        "SLA días": sla_h / C.HORAS_DIA,
        "En SLA": int(efectivas <= sla_h) if resuelto else None,
        "Horas en espera": _r(detenidas),
        "Resuelto": int(resuelto is not None),
        "Cancelado": int(cancelado),
        "Pendiente equipo": int(pendiente),
        "Vencido": int(pendiente and efectivas > sla_h),
        "Días abierto": _r(efectivas / C.HORAS_DIA, 1) if pendiente else None,
        "Antigüedad": tramo(efectivas / C.HORAS_DIA) if pendiente else "",
        "Reaperturas": t["reaperturas"],
        "Veces en espera": t["veces_en_espera"],
        "Primer contacto": (int(t["reaperturas"] == 0 and t["veces_en_espera"] == 0) if resuelto else None),
        "Conformidad": t["conformidad"],
        "CSAT": t["csat"],
    }


def tablas(db: Almacen, cfg: Config, ahora: datetime | None = None) -> dict[str, list[dict]]:
    ahora = (ahora or datetime.now()).replace(microsecond=0)
    nombres = {p["mail"]: p["nombre"] for p in db.consulta("SELECT mail, nombre FROM personas")}
    estados_por_ticket: dict[int, list[dict]] = {}
    for e in db.eventos(tipo="estado"):
        estados_por_ticket.setdefault(e["ticket_id"], []).append(e)
    tickets, estados = [], []
    numero_de = {}
    for t in db.tickets():
        evs = estados_por_ticket.get(t["id"], [])
        numero_de[t["id"]] = t["numero"]
        tickets.append(fila_ticket(t, evs, nombres, ahora, cfg))
        fin_ticket = t["cerrado_en"] or t["cancelado_en"] or ahora
        cambios = sorted(evs, key=lambda e: (e["en"], e["id"]))
        for i, e in enumerate(cambios):
            # El estado final (Cerrado, Cancelado) entra con 0 horas: cuenta el paso.
            hasta = cambios[i + 1]["en"] if i + 1 < len(cambios) else (
                e["en"] if e["estado_hasta"] in C.FINALES else fin_ticket)
            estados.append({"Número": t["numero"], "Estado desde": e["estado_desde"] or "(inicio)",
                            "Estado": e["estado_hasta"], "Orden estado": C.ORDEN_ESTADO[e["estado_hasta"]],
                            "Fecha cambio": e["en"], "Horas en estado": _r(S.horas_habiles(e["en"], hasta, cfg)),
                            "Usuario": nombres.get(e["usuario"], e["usuario"])})
    encuestas = []
    for e in db.encuestas():
        encuestas.append({
            "Número": numero_de.get(e["ticket_id"], ""), "Ronda": e["ronda"], "Fecha envío": e["enviada_en"],
            "Fecha respuesta": e["respondida_en"],
            "Resultado": e["resultado"], "CSAT": e["csat"], "Comentario": e["comentario"] or "",
            "Respondida": int(e["resultado"] in (C.CONFORME, C.NO_CONFORME)),
            "Horas para responder": (_r(S.horas_habiles(e["enviada_en"], e["respondida_en"], cfg))
                                     if e["resultado"] in (C.CONFORME, C.NO_CONFORME) else None)})
    return {"Tickets": tickets, "Estados": estados, "Encuestas": encuestas,
            "Calendario": calendario(min((t["Fecha"] for t in tickets), default=ahora.date()), ahora.date())}


def calendario(desde: date, hasta: date) -> list[dict]:
    """Del primer día del mes del primer ticket al último día del mes de hoy."""
    inicio = desde.replace(day=1)
    fin = (hasta.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    filas, d = [], inicio
    while d <= fin:
        filas.append({"Fecha": d, "Año": d.year, "Período": f"{d.year}-{d.month:02d}",
                      "Mes nombre": f"{MESES[d.month - 1]} {d.year}", "Mes orden": d.year * 100 + d.month,
                      "Día hábil": int(d.weekday() < 5)})
        d += timedelta(days=1)
    return filas


def a_csv(t: dict[str, list[dict]], carpeta: Path) -> list[Path]:
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, filas in t.items():
        ruta = carpeta / f"{nombre}.csv"
        with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
            if filas:
                w = csv.DictWriter(f, fieldnames=list(filas[0]))
                w.writeheader()
                w.writerows({k: ("" if v is None else v) for k, v in fila.items()} for fila in filas)
        rutas.append(ruta)
    return rutas


def a_dataframes(t: dict[str, list[dict]]):
    """Las mismas tablas como DataFrames, con las fechas como fecha (para Excel y el .pbit)."""
    import pandas as pd
    salida = {}
    for nombre, filas in t.items():
        df = pd.DataFrame(filas)
        for col in df.columns:
            if col.startswith("Fecha"):
                df[col] = pd.to_datetime(df[col])
        salida[nombre] = df
    return salida
