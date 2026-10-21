"""
Las medidas DAX y las páginas del tablero de tickets.

Cada medida de KPI lleva `kpi`: el nombre del indicador en
`tickets_ec.indicadores.kpis`. `armar_tablero.py` evalúa la medida sobre los
datos del .pbit y la compara con ese indicador; si no coinciden, el tablero
no sale.
"""
from __future__ import annotations

T, E, K, ES = "'Tickets'", "'Encuestas'", "'Calendario'", "'Estados'"
PCT, ENTERO, DEC = "0.0%", "#,0", "#,0.0"
ROJO, AMBAR, VERDE = "#E03131", "#F08C00", "#12B886"
#: El semáforo del área: ≥ 85 % verde, 70-84 % ámbar, < 70 % rojo.
SEM_PCT = [("<", 0.70, ROJO), ("<", 0.85, AMBAR), (">=", 0.85, VERDE)]
SEM_VENCIDOS = [(">", 0, ROJO), ("<=", 0, VERDE)]


def _m(nombre, expr, carpeta, formato="", desc="", kpi=None):
    d = {"nombre": nombre, "expresion": expr, "carpeta": carpeta, "formato": formato, "descripcion": desc}
    if kpi:
        d["kpi"] = kpi
    return d


def _conteo(resultado: str) -> str:
    return f"CALCULATE(COUNTROWS({E}), KEEPFILTERS({E}[Resultado] = \"{resultado}\")) + 0"


MEDIDAS = [
    # ---- Volumen ------------------------------------------------------------
    _m("Tickets recibidos", f"COUNTROWS({T}) + 0", "01 · Volumen", ENTERO,
       "Pedidos que entraron en el período (por fecha de creación).", "Tickets recibidos"),
    _m("Tickets resueltos",
       f"VAR ini = MIN({K}[Fecha]) VAR fin = MAX({K}[Fecha]) RETURN "
       # UNA condición con && y no dos argumentos: es lo mismo en Power BI, y
       # no depende de que el evaluador intersecte dos filtros sobre la misma
       # columna (el de la suite pisa el primero con el segundo).
       f"CALCULATE(COUNTROWS({T}), REMOVEFILTERS({K}), KEEPFILTERS(NOT ISBLANK({T}[Fecha resolución día]) && "
       f"{T}[Fecha resolución día] >= ini && {T}[Fecha resolución día] <= fin)) + 0", "01 · Volumen", ENTERO,
       "Pedidos resueltos en el período (por fecha de resolución, entren cuando entren).", "Tickets resueltos"),
    _m("Backlog fin de período",
       f"VAR fin = MAX({K}[Fecha]) RETURN CALCULATE(COUNTROWS({T}), REMOVEFILTERS({K}), KEEPFILTERS({T}[Fecha] <= fin), "
       f"KEEPFILTERS(ISBLANK({T}[Fecha salida backlog]) || {T}[Fecha salida backlog] > fin)) + 0", "01 · Volumen", ENTERO,
       "Pedidos que al último día del período habían entrado y todavía no estaban resueltos ni cancelados.",
       "Backlog fin de período"),
    _m("Pendientes del equipo", f"SUM({T}[Pendiente equipo]) + 0", "01 · Volumen", ENTERO,
       "Hoy en Nuevo, Asignado, En curso o Reabierto (corre el reloj del SLA).", "Pendientes del equipo"),
    _m("Pendientes por antigüedad", "VAR n = [Pendientes del equipo] RETURN IF(n > 0, n)", "01 · Volumen", ENTERO,
       "Pendientes del equipo, sin las categorías vacías (para el gráfico por antigüedad)."),
    _m("Vencidos sin resolver", f"SUM({T}[Vencido]) + 0", "01 · Volumen", ENTERO,
       "Pendientes del equipo que ya pasaron su SLA.", "Vencidos sin resolver"),
    _m("Vencido (pendientes)", "IF([Pendientes del equipo] > 0, [Vencidos sin resolver])", "01 · Volumen", ENTERO,
       "Vencidos sin resolver, en blanco para lo que no está pendiente: la tabla de abiertos muestra sólo abiertos."),
    _m("Cancelados", f"SUM({T}[Cancelado]) + 0", "01 · Volumen", ENTERO, "Pedidos cancelados (duplicados, fuera de alcance o retirados).", "Cancelados"),
    _m("Solicitantes", f"DISTINCTCOUNT({T}[Mail solicitante]) + 0", "01 · Volumen", ENTERO,
       "Personas distintas que pidieron.", "Solicitantes"),
    _m("Áreas que piden", f"DISTINCTCOUNT({T}[Área solicitante]) + 0", "01 · Volumen", ENTERO, "Áreas solicitantes distintas con al menos un pedido.", "Áreas que piden"),
    # ---- Tiempos y SLA -------------------------------------------------------
    _m("% en SLA", f"AVERAGE({T}[En SLA])", "02 · Tiempos y SLA", PCT,
       "De los resueltos, cuántos en el plazo de su tipo y prioridad (horas hábiles, sin el tiempo en espera "
       "del solicitante).", "% en SLA"),
    _m("% respuesta en SLA", f"AVERAGE({T}[Respuesta en SLA])", "02 · Tiempos y SLA", PCT,
       "Primera respuesta del equipo dentro del plazo de su prioridad.", "% respuesta en SLA"),
    _m("Horas primera respuesta", f"AVERAGE({T}[Horas primera respuesta])", "02 · Tiempos y SLA", DEC,
       "Horas hábiles hasta que el equipo respondió o empezó.", "Horas primera respuesta"),
    _m("Días de resolución", f"AVERAGE({T}[Días resolución])", "02 · Tiempos y SLA", DEC,
       "Días hábiles efectivos de la creación a la resolución (sin la espera del solicitante).",
       "Días de resolución"),
    _m("Días de resolución (mediana)", f"PERCENTILEX.INC(CALCULATETABLE({T}, KEEPFILTERS(NOT ISBLANK({T}[Días resolución]))), "
       f"{T}[Días resolución], 0.5)", "02 · Tiempos y SLA", DEC,
       "La mitad se resolvió en menos de esto: no la mueven los pocos pedidos larguísimos.",
       "Días de resolución (mediana)"),
    _m("SLA en días", f"AVERAGE({T}[SLA días])", "02 · Tiempos y SLA", DEC,
       "El plazo de resolución acordado (matriz tipo × prioridad)."),
    _m("Días abierto", f"AVERAGE({T}[Días abierto])", "02 · Tiempos y SLA", DEC,
       "Días hábiles efectivos que llevan abiertos los pendientes."),
    _m("Horas en estado", f"AVERAGE({ES}[Horas en estado])", "02 · Tiempos y SLA", DEC,
       "Horas hábiles promedio que un ticket pasa en cada estado."),
    _m("Pasos por el estado", f"COUNTROWS({ES}) + 0", "02 · Tiempos y SLA", ENTERO,
       "Cuántas veces un ticket entró al estado."),
    # ---- Calidad y conformidad ----------------------------------------------
    _m("Tasa de reapertura",
       f"DIVIDE(CALCULATE(COUNTROWS({T}), KEEPFILTERS({T}[Resuelto] = 1), KEEPFILTERS({T}[Reaperturas] > 0)), "
       f"CALCULATE(COUNTROWS({T}), KEEPFILTERS({T}[Resuelto] = 1)))", "03 · Conformidad", PCT,
       "Resueltos que el solicitante devolvió al menos una vez («No conforme»).", "Tasa de reapertura"),
    _m("% sin idas y vueltas", f"AVERAGE({T}[Primer contacto])", "03 · Conformidad", PCT,
       "Resueltos sin pedir datos al solicitante y sin reaperturas.", "% sin idas y vueltas"),
    _m("Encuestas enviadas", f"COUNTROWS({E}) + 0", "03 · Conformidad", ENTERO, "Encuestas de conformidad enviadas (una por cada resolución, incluidas las de tickets reabiertos).", "Encuestas enviadas"),
    _m("Conformes", _conteo("Conforme"), "03 · Conformidad", ENTERO, "Encuestas respondidas «Sí, conforme»."),
    _m("No conformes", _conteo("No conforme"), "03 · Conformidad", ENTERO,
       "Encuestas respondidas «No, falta algo»: cada una reabre el ticket."),
    _m("Conformidad tácita", _conteo("Tácita"), "03 · Conformidad", ENTERO,
       "Cerrados sin respuesta a la encuesta en los días hábiles de gracia."),
    _m("% de respuesta a la encuesta",
       "DIVIDE([Conformes] + [No conformes], [Conformes] + [No conformes] + [Conformidad tácita])",
       "03 · Conformidad", PCT, "Encuestas respondidas sobre encuestas cerradas (respondidas + tácitas).",
       "% de respuesta a la encuesta"),
    _m("% conformidad", "DIVIDE([Conformes], [Conformes] + [No conformes])", "03 · Conformidad", PCT,
       "De los que respondieron la encuesta, cuántos quedaron conformes.", "% conformidad"),
    _m("% conformidad con tácita",
       "DIVIDE([Conformes] + [Conformidad tácita], [Conformes] + [No conformes] + [Conformidad tácita])",
       "03 · Conformidad", PCT, "Cuenta como conforme el silencio después de los días de gracia.",
       "% conformidad con tácita"),
    _m("Satisfacción (1 a 5)", f"AVERAGE({E}[CSAT])", "03 · Conformidad", "0.00", "Promedio de la nota de 1 a 5 que dejó el solicitante en la encuesta.", "Satisfacción (1 a 5)"),
    _m("% satisfechos (4 y 5)",
       f"DIVIDE(CALCULATE(COUNT({E}[CSAT]), KEEPFILTERS({E}[CSAT] >= 4)), COUNT({E}[CSAT]))", "03 · Conformidad", PCT,
       "De las notas de satisfacción, cuántas fueron 4 o 5.", "% satisfechos (4 y 5)"),
    _m("Índice de efectividad",
       "VAR s = [% en SLA] VAR c = [% conformidad con tácita] VAR r = [Tasa de reapertura] RETURN "
       "IF(NOT ISBLANK(s) && NOT ISBLANK(c) && NOT ISBLANK(r), 0.4 * s + 0.4 * c + 0.2 * (1 - r))",
       "03 · Conformidad", PCT,
       "40 % cumplir el plazo + 40 % conformidad (con tácita) + 20 % que no vuelva (1 − reapertura).",
       "Índice de efectividad"),
    # ---- Notas y signos de las tarjetas ----------------------------------
    _m("Nota recibidos", "FORMAT([Tickets resueltos], \"#,0\") & \" resueltos en el período\"", "04 · Notas", "", "Texto debajo de la tarjeta de recibidos."),
    _m("Signo flujo", "[Tickets resueltos] - [Tickets recibidos]", "04 · Notas", ENTERO,
       "Positivo: salió más de lo que entró (el backlog baja)."),
    _m("Nota backlog", "FORMAT([Vencidos sin resolver], \"#,0\") & \" vencidos sin resolver\"", "04 · Notas", "", "Texto debajo de la tarjeta de backlog."),
    _m("Signo vencidos", "0 - [Vencidos sin resolver]", "04 · Notas", ENTERO, "Negativo si hay vencidos: pinta de rojo la nota."),
    _m("Nota SLA", "FORMAT([% respuesta en SLA], \"0%\") & \" de primeras respuestas en plazo · meta 85 %\"",
       "04 · Notas", "", "Texto debajo de la tarjeta de SLA."),
    _m("Signo SLA", "[% en SLA] - 0.85", "04 · Notas", PCT, "Distancia a la meta de 85 %: pinta la nota de verde o rojo."),
    _m("Nota resolución", "\"mediana \" & FORMAT([Días de resolución (mediana)], \"0.0\") & \" días hábiles\"",
       "04 · Notas", "", "Texto debajo de la tarjeta de días de resolución."),
    _m("Nota conformidad", "FORMAT([% de respuesta a la encuesta], \"0%\") & \" respondió la encuesta\"",
       "04 · Notas", "", "Texto debajo de la tarjeta de conformidad."),
    _m("Signo conformidad", "[% conformidad con tácita] - 0.85", "04 · Notas", PCT, "Distancia a la meta de 85 %."),
    _m("Nota índice", "\"40 % SLA · 40 % conformidad · 20 % sin reapertura\"", "04 · Notas", "",
       "Cómo se arma el índice de efectividad."),
    _m("Signo índice", "[Índice de efectividad] - 0.85", "04 · Notas", PCT, "Distancia a la meta de 85 %."),
    _m("Nota satisfacción", "FORMAT([% satisfechos (4 y 5)], \"0%\") & \" puso 4 o 5\"", "04 · Notas", "",
       "Texto debajo de la tarjeta de satisfacción."),
]

RELACIONES = [("Tickets", "Fecha", "Calendario", "Fecha"),
              ("Estados", "Número", "Tickets", "Número"),
              ("Encuestas", "Número", "Tickets", "Número")]
ORDEN = {("Tickets", "Estado"): "Orden estado", ("Estados", "Estado"): "Orden estado",
         ("Tickets", "Prioridad"): "Orden prioridad", ("Calendario", "Mes nombre"): "Mes orden"}

FILTROS = [("Tickets", "Equipo resolutor"), ("Tickets", "Tipo de ticket"), ("Tickets", "Área solicitante"),
           ("Tickets", "Unidad de negocio"), ("Tickets", "País")]
MES = ("Calendario", "Mes nombre")


def _kpi(medida, etiqueta, nota=None, signo=None):
    return {"tipo": "kpi", "medida": medida, "etiqueta": etiqueta, "nota": nota, "signo": signo}


def _kpis(*p):
    return {"alto": 104, "piezas": list(p)}


def _fila(*p, alto=None):
    return {"piezas": list(p), **({"alto": alto} if alto else {})}


def _tabla(titulo, por, medidas, semaforo=None, peso=1):
    return {"tipo": "tabla", "titulo": titulo, "por": por, "medidas": medidas, "semaforo": semaforo or {},
            "peso": peso}


SEM_TABLA = {"% en SLA": SEM_PCT, "% conformidad con tácita": SEM_PCT, "Índice de efectividad": SEM_PCT,
             "Vencidos sin resolver": SEM_VENCIDOS}

PAGINAS = [
    {"titulo": "Resumen ejecutivo", "pregunta": "¿Cuánto entra, cuánto sale y con qué calidad?",
     "filtros": FILTROS,
     "filas": [
         _kpis(_kpi("Tickets recibidos", "Recibidos", "Nota recibidos", "Signo flujo"),
               _kpi("Backlog fin de período", "Backlog", "Nota backlog", "Signo vencidos"),
               _kpi("% en SLA", "En SLA", "Nota SLA", "Signo SLA"),
               _kpi("Días de resolución", "Días de resolución", "Nota resolución"),
               _kpi("% conformidad con tácita", "Conformidad", "Nota conformidad", "Signo conformidad"),
               _kpi("Índice de efectividad", "Índice de efectividad", "Nota índice", "Signo índice")),
         _fila({"tipo": "combo", "medidas": ["Tickets recibidos", "Tickets resueltos"], "por": MES, "peso": 3,
                "titulo": "Recibidos (columnas) y resueltos (línea) por mes"},
               {"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Tipo de ticket"), "peso": 2,
                "titulo": "Qué se pide"}),
         _fila(_tabla("Por equipo resolutor", [("Tickets", "Equipo resolutor")],
                      ["Tickets recibidos", "Tickets resueltos", "Pendientes del equipo", "Vencidos sin resolver",
                       "Días de resolución", "% en SLA", "% conformidad con tácita", "Índice de efectividad"],
                      SEM_TABLA))]},
    {"titulo": "Tickets mensuales", "pregunta": "¿Entra más de lo que sale? ¿Crece el backlog?",
     "filtros": FILTROS,
     "filas": [
         _fila({"tipo": "combo", "medidas": ["Tickets recibidos", "Tickets resueltos"], "por": MES, "peso": 1,
                "titulo": "Recibidos y resueltos"},
               {"tipo": "linea", "medidas": ["Backlog fin de período"], "por": MES, "peso": 1,
                "titulo": "Backlog al cierre de cada mes"}),
         _fila(_tabla("Mes a mes", [MES], ["Tickets recibidos", "Tickets resueltos", "Backlog fin de período",
                                           "Días de resolución", "% en SLA", "% conformidad con tácita",
                                           "Satisfacción (1 a 5)", "Índice de efectividad"], SEM_TABLA))]},
    {"titulo": "Quién pide", "pregunta": "¿De quién, de qué área y de qué país llegan los pedidos?",
     "filtros": [("Tickets", "Equipo resolutor"), ("Tickets", "Tipo de ticket"), ("Calendario", "Año")],
     "filas": [
         _kpis(_kpi("Solicitantes", "Solicitantes"), _kpi("Áreas que piden", "Áreas que piden"),
               _kpi("Tickets recibidos", "Recibidos", "Nota recibidos")),
         _fila({"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Área solicitante"),
                "peso": 1, "titulo": "Por área solicitante"},
               {"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "País"), "peso": 1,
                "titulo": "Por país"},
               {"tipo": "anillo", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Canal"), "peso": 1,
                "titulo": "Por canal"}),
         _fila(_tabla("Solicitantes", [("Tickets", "Solicitante"), ("Tickets", "Área solicitante"), ("Tickets", "País")],
                      ["Tickets recibidos", "Días de resolución", "% en SLA", "% conformidad con tácita",
                       "Satisfacción (1 a 5)"], SEM_TABLA))]},
    {"titulo": "Qué piden", "pregunta": "¿Qué tipo de pedido, de qué área terapéutica, ATC y mercado?",
     "filtros": [("Tickets", "Equipo resolutor"), ("Tickets", "Área solicitante"), ("Tickets", "Área terapéutica"),
                 ("Tickets", "Unidad de negocio"), ("Calendario", "Año")],
     "filas": [
         _fila({"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Tipo de ticket"), "peso": 1,
                "titulo": "Tipo de ticket"},
               _tabla("Tipo y subtipo", [("Tickets", "Tipo de ticket"), ("Tickets", "Subtipo")],
                      ["Tickets recibidos", "Días de resolución", "% en SLA"], SEM_TABLA, peso=2)),
         _fila({"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Área terapéutica"),
                "peso": 1, "titulo": "Área terapéutica (por ATC)"},
               {"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Unidad de negocio"),
                "peso": 1, "titulo": "Unidad de negocio"},
               _tabla("Mercado y ATC", [("Tickets", "Mercado"), ("Tickets", "ATC")], ["Tickets recibidos"], peso=1),
               {"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Fuente de datos"),
                "peso": 1, "titulo": "Fuente de datos"})]},
    {"titulo": "Tiempos y SLA", "pregunta": "¿Respondemos y resolvemos en el plazo acordado?",
     "filtros": FILTROS,
     "filas": [
         _kpis(_kpi("Horas primera respuesta", "Horas a la 1.ª respuesta", "Nota SLA"),
               _kpi("% respuesta en SLA", "1.ª respuesta en plazo"),
               _kpi("Días de resolución", "Días de resolución", "Nota resolución"),
               _kpi("% en SLA", "Resueltos en SLA", None, "Signo SLA"),
               _kpi("Vencidos sin resolver", "Vencidos", None, "Signo vencidos")),
         _fila({"tipo": "linea", "medidas": ["% en SLA", "% respuesta en SLA"], "por": MES, "peso": 3,
                "titulo": "Cumplimiento de SLA por mes"},
               _tabla("Tiempo en cada estado", [("Estados", "Estado")], ["Horas en estado", "Pasos por el estado"],
                      peso=2)),
         _fila(_tabla("Por tipo y prioridad", [("Tickets", "Tipo de ticket"), ("Tickets", "Prioridad")],
                      ["Tickets recibidos", "SLA en días", "Días de resolución", "Días de resolución (mediana)",
                       "% en SLA"], SEM_TABLA))]},
    {"titulo": "Equipo", "pregunta": "¿Cómo se reparte la carga y cómo rinde cada analista?",
     "filtros": [("Tickets", "Equipo resolutor"), ("Tickets", "Tipo de ticket"), ("Calendario", "Año")],
     "filas": [
         _fila({"tipo": "barras", "medidas": ["Pendientes del equipo"], "por": ("Tickets", "Analista"), "peso": 1,
                "titulo": "Pendientes hoy por analista"},
               {"tipo": "barras", "medidas": ["Tickets recibidos"], "por": ("Tickets", "Analista"), "peso": 1,
                "titulo": "Tickets por analista"}),
         _fila(_tabla("Rendimiento por analista", [("Tickets", "Equipo resolutor"), ("Tickets", "Analista")],
                      ["Tickets recibidos", "Pendientes del equipo", "Vencidos sin resolver", "Días de resolución",
                       "% en SLA", "Tasa de reapertura", "% conformidad con tácita", "Satisfacción (1 a 5)",
                       "Índice de efectividad"], SEM_TABLA))]},
    {"titulo": "Conformidad", "pregunta": "¿Quedan conformes quienes piden?",
     "filtros": FILTROS,
     "filas": [
         _kpis(_kpi("% conformidad", "Conformidad (respondidas)", "Nota conformidad", "Signo conformidad"),
               _kpi("% conformidad con tácita", "Con tácita"),
               _kpi("Satisfacción (1 a 5)", "Satisfacción", "Nota satisfacción"),
               _kpi("Tasa de reapertura", "Reapertura"),
               _kpi("% sin idas y vueltas", "Sin idas y vueltas")),
         _fila({"tipo": "columnas", "medidas": ["Conformes", "No conformes", "Conformidad tácita"], "por": MES,
                "peso": 3, "titulo": "Resultado de la encuesta por mes"},
               _tabla("Por área solicitante", [("Tickets", "Área solicitante")],
                      ["Encuestas enviadas", "% de respuesta a la encuesta", "% conformidad",
                       "% conformidad con tácita", "Satisfacción (1 a 5)"], SEM_TABLA, peso=2))]},
    {"titulo": "Backlog y antigüedad", "pregunta": "¿Qué está abierto, desde cuándo y de quién es?",
     "filtros": [("Tickets", "Equipo resolutor"), ("Tickets", "Analista"), ("Tickets", "Tipo de ticket")],
     "filas": [
         _kpis(_kpi("Pendientes del equipo", "Pendientes", "Nota backlog", "Signo vencidos"),
               _kpi("Vencidos sin resolver", "Vencidos", None, "Signo vencidos"),
               _kpi("Días abierto", "Días abiertos (promedio)")),
         _fila({"tipo": "columnas", "medidas": ["Pendientes por antigüedad"], "por": ("Tickets", "Antigüedad"),
                "peso": 1, "titulo": "Pendientes por antigüedad (días hábiles)"},
               _tabla("Lo que está abierto",
                      [("Tickets", c) for c in ("Número", "Asunto", "Solicitante", "Analista", "Estado", "Subestado")],
                      ["Días abierto", "Vencido (pendientes)"], {"Vencido (pendientes)": SEM_VENCIDOS}, peso=3))]},
]
MENU_GRUPOS = {"Resumen ejecutivo": "Gestión", "Tickets mensuales": "Gestión", "Quién pide": "Demanda",
               "Qué piden": "Demanda", "Tiempos y SLA": "Servicio", "Equipo": "Servicio",
               "Conformidad": "Calidad", "Backlog y antigüedad": "Servicio"}
