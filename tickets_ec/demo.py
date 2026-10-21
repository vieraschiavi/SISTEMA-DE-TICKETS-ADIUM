"""
Dieciocho meses de pedidos, simulados con semilla fija y pasando por la
MISMA mesa que usa la app.

No se fabrican filas: se simula la vida de cada pedido (llega por correo o
por el portal, lo asignan, lo toman, a veces piden un dato, se resuelve, el
solicitante da o no su conformidad, a veces se reabre) y cada paso es una
llamada a `Mesa` con el reloj en el momento simulado. Así la demo ejerce las
reglas de verdad —el reloj detenido, la matriz de SLA, el cierre tácito— y el
tablero de Power BI se arma sobre datos que tienen la forma de los reales.

Todo es ficticio: las personas, sus correos (`@adium-demo.test`, un dominio
que no existe) y los pedidos. Los mercados y los ATC sí son los de HQ, porque
son una definición pública del negocio y no datos de nadie.
"""
from __future__ import annotations

import heapq
import itertools
import random
from datetime import datetime, time, timedelta
from pathlib import Path

from . import catalogos as C
from . import clasificador
from . import correo as CO
from . import sla as S
from .almacen import Almacen
from .config import Config
from .servicio import ErrorMesa, Mesa

SEMILLA = 42
DESDE = datetime(2025, 5, 1, 9, 0)
HASTA = datetime(2026, 10, 21, 12, 0)
DOMINIO = "adium-demo.test"

EQUIPO = (
    ("coordinacion.ec", "Coordinación EC (demo)", C.EXCELENCIA, True, 1.0),
    ("ana.pereira", "Ana Pereira (demo)", C.EXCELENCIA, False, 0.9),
    ("bruno.silva", "Bruno Silva (demo)", C.EXCELENCIA, False, 1.0),
    ("carla.mendez", "Carla Méndez (demo)", C.EXCELENCIA, False, 1.15),
    ("diego.rossi", "Diego Rossi (demo)", C.EXCELENCIA, False, 1.35),
    ("elena.suarez", "Elena Suárez (demo)", C.DIGITAL, False, 1.0),
    ("federico.luna", "Federico Luna (demo)", C.DIGITAL, False, 1.2),
)
NOMBRES = ("Lucía", "Martina", "Sofía", "Valentina", "Camila", "Julieta", "Paula", "Florencia", "Agustina", "Mariana",
           "Gabriel", "Nicolás", "Santiago", "Matías", "Joaquín", "Rodrigo", "Pablo", "Andrés", "Tomás", "Ignacio")
APELLIDOS = ("Acosta", "Benítez", "Castro", "Domínguez", "Etcheverry", "Figueroa", "Giménez", "Herrera", "Iglesias",
             "Juárez", "Ledesma", "Morales", "Núñez", "Ortega", "Paredes", "Quiroga", "Ramos", "Sosa", "Torres",
             "Vázquez")
AREAS = (("Marketing", 30), ("Fuerza de Ventas", 14), ("Gerencia de Filial", 12), ("Dirección Comercial", 6),
         ("Finanzas", 8), ("Medical Affairs", 6), ("Acceso al Mercado", 5), ("Business Development / Licencias", 5),
         ("Supply Chain", 6), ("Digital", 3), ("Recursos Humanos", 2), ("IT", 3))
PAISES = (("Uruguay (HQ)", 34), ("Argentina", 10), ("Brasil", 9), ("México", 9), ("Colombia", 7), ("Chile", 6),
          ("Perú", 6), ("Centroamérica", 5), ("Ecuador", 4), ("Paraguay", 4), ("Bolivia", 3), ("Venezuela", 3))
TIPOS = (("Pedido de información", 28), ("Solicitud de permisos", 18), ("Incidente / dato incorrecto", 13),
         ("Cambio en tablero existente", 15), ("Nuevo desarrollo", 10), ("Pedido digital", 10),
         ("Capacitación / consulta", 6))
TABLEROS = ("Informe Dinámico", "Panel Rx", "Cierre PEA", "Stocking Trade", "One BI HQ", "Tracker de pacientes",
            "Venta Interna", "Cuádruple Objetivo")
#: Asuntos por tipo. {m} mercado, {p} país, {t} tablero, {k} KPI.
ASUNTOS = {
    "Pedido de información": ("Share de {m} en {p} (IQVIA TAM)", "Recetas de {m} por especialidad (Close Up)",
                              "Evolutivo de unidades de {m} últimos 12 meses", "Venta interna vs PEA de {p}",
                              "Base de médicos que recetan {m}", "Mercado conformado de {m}",
                              "¿Cuántas unidades vendimos de {m} en {p}?"),
    "Solicitud de permisos": ("Acceso al tablero {t}", "Habilitar mismos accesos que mi compañera en Power BI",
                              "Licencia Power BI Pro para nuevo ingreso", "Acceso a Adaptive consolidado",
                              "Acceso al MDW para {p}", "Permiso de RLS para ver {p} en {t}"),
    "Incidente / dato incorrecto": ("El tablero {t} no actualiza", "Los números de {t} no coinciden con Adaptive",
                                    "Error en un visual de {t}", "{t} muestra {p} en blanco"),
    "Cambio en tablero existente": ("Agregar columna de {k} al tablero {t}", "Agregar filtro de país en {t}",
                                    "Nueva página de {m} en {t}", "Cambiar formato de la matriz de {t}"),
    "Nuevo desarrollo": ("Nuevo tablero de lanzamiento de {m}", "Necesito un tablero de seguimiento de {k}",
                         "Presentación para el comité de {p}", "Automatizar el reporte mensual de {k}",
                         "Modelo con medidas DAX de {k} para {p}"),
    "Pedido digital": ("Mailing de lanzamiento de {m} por Veeva", "Métricas de aperturas del newsletter médico",
                       "Ajuste en el CRM Veeva para {p}", "Landing para webinar de {m}",
                       "Campaña digital de WhatsApp en {p}"),
    "Capacitación / consulta": ("¿Cómo se lee el tablero {t}?", "Capacitación de Power BI para el equipo de {p}",
                                "Duda sobre la fuente de datos de {t}"),
}
KPIS = ("penetración", "cumplimiento PEA", "días de tratamiento", "share", "stock en días", "IE")
#: Esfuerzo típico (fracción del SLA del tipo) y dispersión.
ESFUERZO = {"Solicitud de permisos": (0.45, 0.6), "Incidente / dato incorrecto": (0.5, 0.6),
            "Pedido de información": (0.5, 0.55), "Cambio en tablero existente": (0.55, 0.55),
            "Nuevo desarrollo": (0.6, 0.5), "Pedido digital": (0.5, 0.55), "Capacitación / consulta": (0.35, 0.5)}


def _elegir(rnd: random.Random, pares):
    valores, pesos = zip(*pares, strict=True)
    return rnd.choices(valores, weights=pesos, k=1)[0]


def _persona(rnd: random.Random, i: int) -> dict:
    nombre, apellido = rnd.choice(NOMBRES), rnd.choice(APELLIDOS)
    area = _elegir(rnd, AREAS)
    pais = "Uruguay (HQ)" if area in ("Dirección Comercial", "Business Development / Licencias") else _elegir(rnd, PAISES)
    return {"mail": f"{clasificador.normalizar(nombre)}.{clasificador.normalizar(apellido)}{i}@{DOMINIO}",
            "nombre": f"{nombre} {apellido}", "area": area, "pais": pais}


def _llegadas(rnd: random.Random, desde: datetime, hasta: datetime, cfg: Config):
    """Momentos de llegada: ~4,5 pedidos por día hábil, que crecen con el uso
    de la mesa y suben en el cierre de año y en la planificación (oct-nov)."""
    d = desde.date()
    total = (hasta.date() - d).days or 1
    i = 0
    while d <= hasta.date():
        if d.weekday() < 5 and d not in cfg.feriados:
            crecimiento = 0.75 + 0.5 * (i / total)
            estacion = 1.25 if d.month in (10, 11) else 0.8 if d.month in (1, 7) else 1.0
            n = sum(rnd.random() < 4.5 * crecimiento * estacion / 10 for _ in range(10))
            for _ in range(n):
                hora = rnd.choices((rnd.uniform(8, 9), rnd.uniform(9, 18), rnd.uniform(18, 21)), (1, 12, 1))[0]
                yield datetime.combine(d, time(0)) + timedelta(hours=hora)
        d += timedelta(days=1)
        i += 1


def generar(destino: str | Path = ":memory:", hasta: datetime = HASTA, desde: datetime = DESDE,
            semilla: int = SEMILLA, cfg: Config | None = None) -> Mesa:
    """La mesa con la demo cargada. `destino` es la base SQLite (o memoria)."""
    rnd = random.Random(semilla)
    cfg = cfg or Config(directorio=Path("/dev/null/no-hay-directorio.csv"))
    reloj = [desde]
    mesa = Mesa(Almacen(destino), cfg, CO.BuzonSalida(None), reloj=lambda: reloj[0], guardar_adjuntos=False)
    habilidad = {}
    for usuario, nombre, equipo, coord, h in EQUIPO:
        mesa.alta_analista(f"{usuario}@{DOMINIO}", nombre, coordinador=coord, equipo=equipo)
        habilidad[f"{usuario}@{DOMINIO}"] = h
    coordinador = f"{EQUIPO[0][0]}@{DOMINIO}"
    personas = [_persona(rnd, i) for i in range(90)]
    for p in personas:
        mesa.db.guardar_persona(p["mail"], p["nombre"], p["area"], p["pais"])
    mercados = [m for m in clasificador.mercados() if m["atc"]]

    cola: list = []
    orden = itertools.count()

    def programar(momento: datetime, accion, *args):
        if momento <= hasta:
            heapq.heappush(cola, (momento, next(orden), accion, args))

    def en(desde_m: datetime, horas: float) -> datetime:
        return S.sumar_horas_habiles(desde_m, max(0.05, horas), cfg)

    # ---- la vida de un pedido ------------------------------------------
    def llega(momento: datetime):
        p = rnd.choice(personas)
        tipo = _elegir(rnd, TIPOS)
        m = rnd.choice(mercados)
        asunto = rnd.choice(ASUNTOS[tipo]).format(m=m["mercado"].title(), p=p["pais"].split(" ")[0],
                                                  t=rnd.choice(TABLEROS), k=rnd.choice(KPIS))
        cuerpo = rnd.choices(("Hola, ¿me ayudan con esto?", "Buen día. Lo necesitamos para la reunión de línea.",
                             "Gracias de antemano.", "Es urgente para mañana, gracias.",
                             "Lo pide la gerencia para el comité.", "Hola, lo necesito para hoy: es crítico."), (8, 8, 8, 3, 6, 1))[0]
        if rnd.random() < 0.55:
            mid = f"<demo-{next(orden)}@{DOMINIO}>"
            r = mesa.procesar_correo(CO.Mensaje(mid, p["mail"], p["nombre"], asunto, cuerpo, momento))
            t = mesa.db.ticket(r.numero)
        else:   # por el portal: el tipo lo elige quien pide
            t = mesa.crear(asunto, cuerpo, p["mail"], p["nombre"], canal="Portal", tipo=tipo)
        programar(en(momento, rnd.uniform(0.1, 2.5)), asignar, t["numero"])

    def asignar(numero: str):
        t = mesa.db.ticket(numero)
        if rnd.random() < 0.04:
            mesa.cancelar(numero, "Lo retiró el solicitante", coordinador, subestado="Lo retiró el solicitante")
            return
        analista = mesa.sugerir_analista(t["equipo"])
        mesa.asignar(numero, analista, coordinador)
        programar(en(reloj[0], rnd.uniform(0.2, 5)), tomar, numero)

    def tomar(numero: str):
        t = mesa.db.ticket(numero)
        mesa.tomar(numero, t["analista_mail"])
        sla_h = C.sla_horas(t["tipo"], t["prioridad"])
        media, disp = ESFUERZO.get(t["tipo"], (0.5, 0.55))
        esfuerzo = sla_h * media * habilidad[t["analista_mail"]] * rnd.lognormvariate(0, disp)
        if rnd.random() < 0.22:          # le falta un dato
            programar(en(reloj[0], esfuerzo * rnd.uniform(0.1, 0.4)), pedir_dato, numero, esfuerzo)
        else:
            programar(en(reloj[0], esfuerzo), resolver, numero)

    def pedir_dato(numero: str, esfuerzo: float):
        t = mesa.db.ticket(numero)
        mesa.pedir_informacion(numero, "¿Para qué país y período lo necesitás?", t["analista_mail"])
        programar(en(reloj[0], rnd.uniform(1, 25)), contesta, numero, esfuerzo)

    def contesta(numero: str, esfuerzo: float):
        t = mesa.db.ticket(numero)
        mid = f"<demo-{next(orden)}@{DOMINIO}>"
        mesa.procesar_correo(CO.Mensaje(mid, t["solicitante_mail"], t["solicitante_nombre"],
                                        f"RE: [{numero}] {t['asunto']}", "Para todos los países, TAM.", reloj[0]))
        programar(en(reloj[0], esfuerzo * rnd.uniform(0.4, 0.8)), resolver, numero)

    def resolver(numero: str):
        t = mesa.db.ticket(numero)
        t = mesa.resolver(numero, "Listo: te dejamos el resultado en el link del tablero.", t["analista_mail"])
        responde = rnd.random() < 0.68
        if responde:
            demora = mesa.estado_sla(t)["semaforo"] == "Vencido"
            conforme = rnd.random() < (0.72 if demora else 0.9)
            programar(en(reloj[0], rnd.uniform(0.2, 20)), opina, t["_token"], conforme, demora)

    def opina(token: str, conforme: bool, demora: bool):
        if conforme:
            csat = rnd.choices((3, 4, 5), (1, 4, 6) if not demora else (3, 4, 2))[0]
            t = mesa.responder_encuesta(token, True, csat)
        else:
            t = mesa.responder_encuesta(token, False, rnd.choice((1, 2, 3)), "Falta abrir por país.")
            programar(en(reloj[0], rnd.uniform(0.5, 6)), retoma, t["numero"])

    def retoma(numero: str):
        t = mesa.db.ticket(numero)
        mesa.tomar(numero, t["analista_mail"])
        programar(en(reloj[0], rnd.uniform(1, 12)), resolver, numero)

    def barrer():
        mesa.cierre_tacito()

    for momento in _llegadas(rnd, desde, hasta, cfg):
        programar(momento, llega, momento)
    d = desde.date()
    while d <= hasta.date():
        programar(datetime.combine(d, time(9, 5)), barrer)
        d += timedelta(days=1)

    while cola:
        momento, _n, accion, args = heapq.heappop(cola)
        reloj[0] = momento
        try:
            accion(*args)
        except ErrorMesa:
            pass          # p. ej. un cierre tácito que ganó de mano a una respuesta tardía
    reloj[0] = hasta
    return mesa


if __name__ == "__main__":      # python -m tickets_ec.demo [ruta.db]
    import sys

    from .config import cargar
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else cargar().base
    if ruta.exists():
        sys.exit(f"{ruta} ya existe: la demo no pisa una base. Borrala a mano si querés regenerarla.")
    m = generar(ruta)
    print(f"Demo cargada en {ruta}: {len(m.db.tickets())} tickets.")
