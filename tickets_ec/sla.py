"""
El reloj de la mesa: horas hábiles, vencimientos y cumplimiento de SLA.

Un pedido que entra el viernes a las 17:30 y se resuelve el lunes a las 10
no tardó 64 horas: tardó una y media. Medir en horas corridas castiga al
equipo por los fines de semana y premia al que resuelve los lunes, así que
todo se mide en horas HÁBILES (de `hora_inicio` a `hora_fin`, lunes a
viernes, sin feriados).

Y el reloj se DETIENE mientras el ticket espera al solicitante («En espera
del solicitante» o «Resuelto» esperando la conformidad): si el analista
pidió un dato y el solicitante tardó tres días en mandarlo, esos tres días
no son del equipo.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import catalogos as C
from .config import Config


def _es_habil(d: date, cfg: Config) -> bool:
    return d.weekday() < 5 and d not in cfg.feriados


def horas_habiles(desde: datetime, hasta: datetime, cfg: Config) -> float:
    """Horas hábiles entre dos momentos (0 si `hasta` no es posterior)."""
    if hasta <= desde:
        return 0.0
    total = 0.0
    dia = desde.date()
    while dia <= hasta.date():
        if _es_habil(dia, cfg):
            abre = datetime.combine(dia, time(cfg.hora_inicio))
            cierra = datetime.combine(dia, time(cfg.hora_fin))
            a, b = max(abre, desde), min(cierra, hasta)
            if b > a:
                total += (b - a).total_seconds() / 3600
        dia += timedelta(days=1)
    return total


def sumar_horas_habiles(desde: datetime, horas: float, cfg: Config) -> datetime:
    """El momento en que se cumplen `horas` hábiles contadas desde `desde`."""
    restante = max(0.0, horas)
    actual = desde
    while True:
        dia = actual.date()
        if _es_habil(dia, cfg):
            abre = datetime.combine(dia, time(cfg.hora_inicio))
            cierra = datetime.combine(dia, time(cfg.hora_fin))
            inicio = max(actual, abre)
            if inicio < cierra:
                disponible = (cierra - inicio).total_seconds() / 3600
                if restante <= disponible + 1e-9:
                    return inicio + timedelta(hours=restante)
                restante -= disponible
        actual = datetime.combine(dia + timedelta(days=1), time(cfg.hora_inicio))


def tramos_de_estado(eventos: list[dict], hasta: datetime) -> list[tuple[str, datetime, datetime]]:
    """[(estado, desde, hasta)] a partir de los cambios de estado ordenados.

    `eventos`: dicts con `en` (datetime) y `estado_hasta`, sólo los de tipo
    estado. El último tramo queda abierto hasta `hasta` (ahora, o el cierre).
    """
    cambios = sorted((e for e in eventos if e.get("estado_hasta")), key=lambda e: e["en"])
    tramos = []
    for i, e in enumerate(cambios):
        fin = cambios[i + 1]["en"] if i + 1 < len(cambios) else hasta
        if fin > e["en"]:
            tramos.append((e["estado_hasta"], e["en"], fin))
    return tramos


def horas_detenidas(eventos: list[dict], hasta: datetime, cfg: Config) -> float:
    """Horas hábiles con el reloj detenido (esperando al solicitante) ANTES
    de `hasta`. «Resuelto» cuenta sólo si después se reabrió: la espera de
    conformidad de un ticket que se cierra no es tiempo de resolución."""
    total = 0.0
    for estado, a, b in tramos_de_estado(eventos, hasta):
        if estado in C.RELOJ_DETENIDO:
            total += horas_habiles(a, min(b, hasta), cfg)
    return total


def horas_efectivas(creado: datetime, hasta: datetime, eventos: list[dict], cfg: Config) -> float:
    """Horas hábiles del equipo: de la creación a `hasta`, menos las detenidas."""
    return max(0.0, horas_habiles(creado, hasta, cfg) - horas_detenidas(eventos, hasta, cfg))


def vencimiento(creado: datetime, tipo: str, prioridad: str, eventos: list[dict], ahora: datetime,
                cfg: Config) -> datetime:
    """Cuándo vence la resolución, corrido por todo el tiempo detenido hasta ahora."""
    return sumar_horas_habiles(creado, C.sla_horas(tipo, prioridad) + horas_detenidas(eventos, ahora, cfg), cfg)


def semaforo(horas_usadas: float, tipo: str, prioridad: str) -> str:
    """«En plazo» hasta el 75 % del SLA, «Por vencer» hasta el 100 %, «Vencido» después."""
    limite = C.sla_horas(tipo, prioridad)
    uso = horas_usadas / limite if limite else 0
    if uso > 1:
        return "Vencido"
    if uso > 0.75:
        return "Por vencer"
    return "En plazo"
