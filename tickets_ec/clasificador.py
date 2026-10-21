"""
Del correo al ticket: qué tipo de pedido es, qué prioridad tiene y de qué
área y país viene quien lo manda.

Es un clasificador de reglas, no un modelo: con cien tickets por mes no hay
datos para entrenar nada honesto, y una regla se puede leer y discutir. Cada
decisión deja escrito POR QUÉ (`Clasificacion.motivo`), que queda en el
ticket: el analista que lo corrige ve qué palabra lo llevó ahí.

El área NO se adivina del texto. Sale del directorio (la exportación de Entra
ID / Active Directory en `datos/directorio.csv`, o lo que se cargó a mano en
la mesa); sin directorio, el país sale del dominio del correo y el área queda
«Sin área» para que alguien la complete. Un tablero «por área» con áreas
inventadas por palabras clave es peor que uno con un «Sin área» honesto.
"""
from __future__ import annotations

import csv
import functools
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from . import catalogos as C
from .config import Config


def normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sin_acentos if not unicodedata.combining(c)).lower()


MERCADOS = Path(__file__).resolve().parent / "datos" / "mercados_conformados.csv"


@dataclass(frozen=True)
class Clasificacion:
    equipo: str
    tipo: str
    subtipo: str
    prioridad: str
    area: str
    pais: str
    atc: str
    area_terapeutica: str
    unidad_negocio: str
    mercado: str
    fuente_datos: str
    motivo: str


@dataclass(frozen=True)
class SobreQue:
    atc: str
    area_terapeutica: str
    unidad_negocio: str
    mercado: str
    fuente_datos: str
    motivo: str


@functools.lru_cache(maxsize=4)
def mercados(ruta: Path = MERCADOS) -> tuple[dict, ...]:
    """Los mercados conformados de HQ (ver `scripts/importar_mercados.py`)."""
    if not Path(ruta).is_file():
        return ()
    with open(ruta, encoding="utf-8", newline="") as f:
        return tuple(csv.DictReader(f))


#: Una clase terapéutica escrita en el pedido: «A10», «C10A1», «A02B2».
#: Sin O ni Q de primera letra (no hay grupos ATC con esas) y con borde de
#: palabra a los dos lados, para no leer «B12» adentro de «vitamina B12x».
_ATC = re.compile(r"\b([A-NP-V]\d{2}(?:[A-Z]\d?)?)\b")


def sobre_que(asunto: str, cuerpo: str) -> SobreQue:
    """ATC, área terapéutica, mercado y fuente que nombra el pedido.

    El mercado gana: si el pedido nombra «rosuvastatina», el ATC sale de la
    definición de HQ de ese mercado. Si no, se busca un código ATC escrito.
    El área terapéutica sale SIEMPRE del ATC con la regla del manual, no del
    texto: «cardio» en un pedido de Finanzas no lo vuelve cardiovascular.
    """
    texto_n = normalizar(f"{asunto} {cuerpo}")
    atc, mercado, motivo = "", "", []
    # El nombre más largo primero: «ROSUVASTATINA + EZETIMIBE» antes que «ROSUVASTATINA».
    for m in sorted(mercados(), key=lambda m: -len(m["mercado"])):
        nombre = normalizar(m["mercado"]).split("(")[0].strip()
        if len(nombre) >= 5 and re.search(rf"\b{re.escape(nombre)}\b", texto_n):
            atc, mercado = m["atc"], m["mercado"]
            motivo.append(f"mercado «{mercado}»")
            break
    if not atc:
        codigos = _ATC.findall(f"{asunto} {cuerpo}".upper())
        if codigos:
            atc = codigos[0]
            motivo.append(f"ATC «{atc}» escrito en el pedido")
    area_t = (C.area_terapeutica(atc) or "Otra") if atc else C.AREA_TERAPEUTICA_DEFECTO
    if not atc:
        nombrada = next((a for a in C.AREAS_TERAPEUTICAS[:8]
                         if normalizar(a.split(" & ")[0]) in texto_n), None)
        if nombrada:
            area_t = nombrada
            motivo.append(f"área terapéutica «{nombrada}» nombrada")
    fuente = next((f for f, palabras in C.PALABRAS_FUENTE.items() if any(p in texto_n for p in palabras)),
                  C.FUENTE_DEFECTO)
    if fuente != C.FUENTE_DEFECTO:
        motivo.append(f"fuente {fuente}")
    un = C.unidad_negocio(atc, mercado) if atc else C.UNIDAD_NEGOCIO_DEFECTO
    return SobreQue(atc, area_t, un, mercado, fuente, ", ".join(motivo) or "sin mercado, ATC ni fuente")


def subtipo(tipo: str, asunto: str, cuerpo: str) -> str:
    """El subtipo con más palabras en el texto; sin ninguna, el primero del tipo."""
    t = C.POR_TIPO.get(tipo, C.POR_TIPO[C.TIPO_DEFECTO])
    texto_n = normalizar(f"{asunto} {asunto} {cuerpo}")
    puntos = {s: sum(texto_n.count(p) for p in palabras) for s, palabras in t.subtipos.items()}
    mejor = max(puntos, key=lambda s: puntos[s])
    return mejor if puntos[mejor] else next(iter(t.subtipos))


def tipo_y_prioridad(asunto: str, cuerpo: str) -> tuple[str, str, str]:
    """(tipo, prioridad, motivo). El asunto pesa el doble que el cuerpo:
    es lo que la persona eligió para resumir el pedido."""
    a, c = normalizar(asunto), normalizar(cuerpo)
    mejor, puntos_mejor, palabras_mejor = C.TIPO_DEFECTO, 0.0, []
    for t in C.TIPOS:
        puntos, usadas = 0.0, []
        for palabra in t.palabras:
            peso = len(palabra.split())         # una frase vale más que una palabra suelta
            # Borde de palabra sólo al principio: «incorrect» calza en «incorrecto»
            # pero «pea» no calza en «golpea».
            patron = re.compile(rf"\b{re.escape(palabra)}")
            if patron.search(a):
                puntos += 2 * peso
                usadas.append(palabra)
            elif patron.search(c):
                puntos += peso
                usadas.append(palabra)
        if puntos > puntos_mejor:
            mejor, puntos_mejor, palabras_mejor = t.nombre, puntos, usadas
    prioridad = C.POR_TIPO[mejor].prioridad
    motivo = (f"tipo «{mejor}» por: {', '.join(palabras_mejor[:4])}" if palabras_mejor
              else "sin palabras clave: tipo «Otro»")
    texto = f"{a} {c}"
    critica = next((p for p in C.URGENCIA_CRITICA if p in texto), None)
    alta = next((p for p in C.URGENCIA_ALTA if p in texto), None)
    if critica:
        prioridad, motivo = "Crítica", f"{motivo}; prioridad Crítica por «{critica}»"
    elif alta and C.POR_PRIORIDAD[prioridad].orden > C.POR_PRIORIDAD["Alta"].orden:
        prioridad, motivo = "Alta", f"{motivo}; prioridad Alta por «{alta}»"
    else:
        motivo = f"{motivo}; prioridad {prioridad} (la del tipo)"
    return mejor, prioridad, motivo


def equipo_resolutor(tipo: str, asunto: str, cuerpo: str) -> tuple[str, str]:
    """(equipo, motivo). El del tipo, salvo que el pedido nombre algo de Digital."""
    t = C.POR_TIPO.get(tipo, C.POR_TIPO[C.TIPO_DEFECTO])
    if t.equipo == C.DIGITAL:
        return C.DIGITAL, "equipo Digital (por el tipo)"
    texto = normalizar(f"{asunto} {cuerpo}")
    palabra = next((p for p in C.PALABRAS_DIGITAL if re.search(rf"\b{re.escape(p)}\b", texto)), None)
    if palabra:
        return C.DIGITAL, f"equipo Digital por «{palabra}»"
    return t.equipo, f"equipo {t.equipo}"


def leer_directorio(ruta: Path) -> dict[str, dict]:
    """`mail,nombre,area,pais` (la primera fila son los encabezados)."""
    if not Path(ruta).is_file():
        return {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return {(fila.get("mail") or "").strip().lower(): fila for fila in csv.DictReader(f)
                if (fila.get("mail") or "").strip()}


def area_y_pais(mail: str, persona: dict | None, cfg: Config) -> tuple[str, str, str]:
    """(área, país, de dónde salió)."""
    if persona and (persona.get("area") or persona.get("pais")):
        return (persona.get("area") or C.AREA_DEFECTO, persona.get("pais") or C.PAIS_DEFECTO, "directorio")
    dominio = mail.rsplit("@", 1)[-1].lower()
    pais = cfg.pais_por_dominio.get(dominio)
    if pais:
        return C.AREA_DEFECTO, pais, f"país por el dominio {dominio}; área a completar"
    return C.AREA_DEFECTO, C.PAIS_DEFECTO, "fuera del directorio: área y país a completar"


def clasificar(asunto: str, cuerpo: str, mail: str, persona: dict | None, cfg: Config) -> Clasificacion:
    tipo, prioridad, motivo = tipo_y_prioridad(asunto, cuerpo)
    area, pais, origen = area_y_pais(mail, persona, cfg)
    q = sobre_que(asunto, cuerpo)
    equipo, motivo_eq = equipo_resolutor(tipo, asunto, cuerpo)
    motivo = f"{motivo}; {motivo_eq}"
    return Clasificacion(equipo, tipo, subtipo(tipo, asunto, cuerpo), prioridad, area, pais, q.atc, q.area_terapeutica,
                         q.unidad_negocio, q.mercado, q.fuente_datos, f"{motivo}; sobre qué: {q.motivo}; área y país: {origen}")
