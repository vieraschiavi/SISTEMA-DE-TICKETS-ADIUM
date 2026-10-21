"""
Los catálogos de la mesa: estados, tipos de pedido, prioridades con su SLA,
áreas y países de Adium.

Están en un solo lugar porque los usan cuatro lados que no pueden
desincronizarse: el clasificador del correo, la app, el export a Power BI y
el DAX del tablero (que filtra por el TEXTO de estos valores). Un estado que
se renombra acá y no en el DAX deja una tarjeta en blanco sin error.
"""
from __future__ import annotations

from dataclasses import dataclass

# ==========================================================================
# Estados
# ==========================================================================
NUEVO = "Nuevo"
ASIGNADO = "Asignado"
EN_CURSO = "En curso"
EN_ESPERA = "En espera del solicitante"
RESUELTO = "Resuelto"
REABIERTO = "Reabierto"
CERRADO = "Cerrado"
CANCELADO = "Cancelado"

ESTADOS = (NUEVO, ASIGNADO, EN_CURSO, EN_ESPERA, RESUELTO, REABIERTO, CERRADO, CANCELADO)

#: El orden en que se leen en un tablero (flujo, no alfabético).
ORDEN_ESTADO = {e: i for i, e in enumerate(ESTADOS, start=1)}

#: Qué transición puede hacer una persona del equipo. RESUELTO → CERRADO y
#: RESUELTO → REABIERTO no figuran: las decide el SOLICITANTE con la
#: encuesta de conformidad (o el cierre tácito), nunca el analista. Así el
#: «% de conformidad» mide lo que dijo quien pidió, no lo que creyó el equipo.
TRANSICIONES: dict[str, frozenset[str]] = {
    NUEVO: frozenset({ASIGNADO, EN_CURSO, EN_ESPERA, RESUELTO, CANCELADO}),
    ASIGNADO: frozenset({EN_CURSO, EN_ESPERA, RESUELTO, CANCELADO}),
    EN_CURSO: frozenset({EN_ESPERA, RESUELTO, CANCELADO}),
    EN_ESPERA: frozenset({EN_CURSO, RESUELTO, CANCELADO}),
    REABIERTO: frozenset({EN_CURSO, EN_ESPERA, RESUELTO, CANCELADO}),
    RESUELTO: frozenset(),
    CERRADO: frozenset(),
    CANCELADO: frozenset(),
}

#: Las que sólo hace el sistema: la conformidad y el cierre tácito.
TRANSICIONES_SISTEMA: dict[str, frozenset[str]] = {
    RESUELTO: frozenset({CERRADO, REABIERTO}),
    EN_ESPERA: frozenset({EN_CURSO}),          # el solicitante contestó el correo
}

#: Subestados: el detalle que el estado no dice (lo mismo que el
#: «240 - En Aprobación» del portal de IT). No cambian el reloj del SLA: lo
#: cambia el estado. «Esperando a IT / fuente» es del equipo aunque la demora
#: sea de otro: el SLA lo mide quien pidió, y para quien pidió la demora es
#: de la mesa.
SUBESTADOS: dict[str, tuple[str, ...]] = {
    NUEVO: ("Sin clasificar",),
    ASIGNADO: ("En cola del analista",),
    EN_CURSO: ("En análisis", "En desarrollo", "Esperando a IT / fuente de datos", "En validación de datos",
               "En aprobación"),
    EN_ESPERA: ("Esperando información", "Esperando aprobación del solicitante", "Esperando validación"),
    RESUELTO: ("Esperando conformidad",),
    REABIERTO: ("No conforme",),
    CERRADO: ("Conforme", "Conformidad tácita"),
    CANCELADO: ("Duplicado", "Fuera de alcance", "Lo retiró el solicitante"),
}


def subestado_defecto(estado: str) -> str:
    return SUBESTADOS.get(estado, ("",))[0]


FINALES = frozenset({CERRADO, CANCELADO})
#: Pendientes del equipo: lo que suma al backlog y corre contra el SLA.
PENDIENTES_EQUIPO = frozenset({NUEVO, ASIGNADO, EN_CURSO, REABIERTO})
#: Esperando al solicitante: el reloj del SLA está detenido.
RELOJ_DETENIDO = frozenset({EN_ESPERA, RESUELTO})


def puede(desde: str, hacia: str, sistema: bool = False) -> bool:
    if hacia in TRANSICIONES.get(desde, frozenset()):
        return True
    return sistema and hacia in TRANSICIONES_SISTEMA.get(desde, frozenset())


# ==========================================================================
# Prioridades
# ==========================================================================
@dataclass(frozen=True)
class Prioridad:
    nombre: str
    orden: int
    horas_respuesta: float      # primera respuesta del equipo, en horas HÁBILES


PRIORIDADES = (
    Prioridad("Crítica", 1, 2),
    Prioridad("Alta", 2, 4),
    Prioridad("Media", 3, 9),
    Prioridad("Baja", 4, 18),
)
POR_PRIORIDAD = {p.nombre: p for p in PRIORIDADES}
PRIORIDAD_DEFECTO = "Media"
#: Horas de un día hábil (9 a 18). El SLA se escribe en días y se mide en horas.
HORAS_DIA = 9


# ==========================================================================
# Tipo de ticket (el filtro principal) y subtipo
# ==========================================================================
# ==========================================================================
# Quién lo resuelve: los dos equipos mancomunados
# ==========================================================================
EXCELENCIA = "Excelencia Comercial"
DIGITAL = "Digital"
EQUIPOS = (EXCELENCIA, DIGITAL)
EQUIPO_DEFECTO = EXCELENCIA
#: Palabras que mandan un pedido a Digital aunque su tipo sea de los
#: generales (un «cambio» en el CRM es de Digital, no de BI).
PALABRAS_DIGITAL = ("veeva", "crm", "mailing", "email marketing", "e-mail marketing", "newsletter", "landing",
                    "pagina web", "sitio web", "redes sociales", "instagram", "linkedin", "whatsapp", "e-detailing",
                    "edetailing", "app movil", "aplicacion movil", "google analytics", "campana digital",
                    "canal digital", "omnicanal", "webinar", "portal medico", "digital")


@dataclass(frozen=True)
class Tipo:
    nombre: str
    prioridad: str
    #: Días hábiles para resolver, por prioridad (Crítica, Alta, Media, Baja).
    #: Un permiso y un tablero nuevo no pueden tener el mismo plazo: con un
    #: SLA único, o los permisos sobran de tiempo o los desarrollos nacen
    #: vencidos y el «% en SLA» deja de decir algo.
    dias: tuple[int, int, int, int]
    palabras: tuple[str, ...]          # sin acentos y en minúscula
    subtipos: dict                     # subtipo -> palabras
    equipo: str = EXCELENCIA           # el que lo recibe por defecto


TIPOS = (
    Tipo("Incidente / dato incorrecto", "Alta", (1, 2, 3, 5),
         ("error", "no coincide", "no cierra", "no actualiza", "falla", "esta mal", "incorrect", "diferencia",
          "no carga", "caido", "en blanco", "duplicad", "no anda", "no funciona", "rompio"),
         {"Dato incorrecto o que no cierra": ("no coincide", "no cierra", "diferencia", "incorrect", "duplicad",
                                              "esta mal"),
          "Tablero que no actualiza": ("no actualiza", "actualizacion", "refresh", "desactualizad"),
          "Visual o tablero con error": ("error", "en blanco", "no carga", "no anda", "no funciona"),
          "Fuente de datos caída": ("caido", "fuente", "conexion", "gateway")}),
    Tipo("Solicitud de permisos", "Alta", (1, 1, 2, 3),
         ("acceso", "acceso al", "acceso a", "permiso", "licencia", "no puedo ver", "no puedo entrar", "compartir", "workspace", "rls",
          "habilitar", "dar de alta", "mismos accesos", "usuario nuevo"),
         {"Acceso a app o workspace de Power BI": ("workspace", "app", "power bi", "tablero", "informe", "compartir"),
          "Acceso por país o marca (RLS)": ("rls", "pais", "filial", "marca"),
          "Acceso a fuente de datos (MDW / Fabric / SQL)": ("mdw", "fabric", "sql", "analysis services", "lakehouse",
                                                            "base"),
          "Acceso a Adaptive": ("adaptive",),
          "Licencia Power BI Pro / Copilot": ("licencia", "pro", "copilot", "premium")}),
    Tipo("Nuevo desarrollo", "Media", (5, 10, 20, 30),
         ("nuevo tablero", "nuevo informe", "nuevo reporte", "armar un tablero", "armar un informe", "dashboard",
          "necesito un tablero", "necesito un informe", "desarrollar", "desarrollo", "automatizar", "proyecto",
          "presentacion", "mazo", "nuevo kpi", "modelo"),
         {"Tablero Power BI nuevo": ("tablero", "dashboard", "power bi", "informe", "reporte"),
          "Modelo de datos o medidas DAX": ("modelo", "medida", "dax", "kpi"),
          "Automatización o proceso de datos": ("automatizar", "proceso", "pipeline", "carga", "fabric"),
          "Presentación o mazo": ("presentacion", "mazo", "slides", "power point", "powerpoint", "directorio",
                                  "comite")}),
    Tipo("Cambio en tablero existente", "Media", (2, 5, 8, 15),
         ("agregar", "cambiar", "modificar", "sumar una columna", "filtro", "segmentador", "nueva pagina", "ajuste",
          "mejora", "agregar una", "sacar", "quitar", "al tablero", "en el tablero", "del tablero", "columna"),
         {"Agregar KPI o columna": ("kpi", "columna", "medida", "indicador", "agregar"),
          "Filtros o segmentadores": ("filtro", "segmentador", "slicer"),
          "Nueva página": ("pagina", "solapa", "pestana"),
          "Formato o diseño": ("formato", "color", "diseno", "titulo")}),
    Tipo("Pedido de información", "Media", (1, 3, 5, 10),
         ("iqvia", "close up", "closeup", "share", "mercado", "recetas", "prescripcion", "penetracion", "evolutivo",
          "base", "extraccion", "extraer", "excel con", "listado", "descargar", "export", "datos de", "necesito el dato",
          "cuanto", "cuanta", "me pasas", "me podes pasar", "informacion", "venta interna", "pea", "unidades",
          "vendimos", "cumplimiento"),
         {"Mercado conformado": ("mercado conformado", "conformar", "canasta", "competidores del mercado"),
          "Consulta de mercado (IQVIA)": ("iqvia", "share", "mercado", "evolutivo", "unidades", "tam", "ytd"),
          "Recetas y médicos (Close Up)": ("close up", "closeup", "recetas", "prescrip", "medicos", "especialidad"),
          "Venta interna / PEA": ("venta interna", "pea", "adaptive", "presupuesto", "cumplimiento"),
          "Extracción de base": ("base", "extraccion", "extraer", "listado", "excel", "export", "descargar"),
          "Dato puntual": ("cuanto", "cuanta", "dato")}),
    Tipo("Pedido digital", "Media", (1, 3, 5, 10),
         ("veeva", "crm", "mailing", "email marketing", "newsletter", "landing", "pagina web", "sitio web",
          "redes sociales", "whatsapp", "e-detailing", "edetailing", "app movil", "google analytics",
          "campana digital", "canal digital", "omnicanal", "webinar", "portal medico"),
         {"CRM / Veeva": ("veeva", "crm", "visita", "call"),
          "Campaña o canal digital": ("mailing", "email", "newsletter", "campana", "whatsapp", "redes", "webinar"),
          "Web, app o e-detailing": ("web", "landing", "app", "e-detailing", "edetailing", "portal"),
          "Analítica digital": ("analytics", "metricas", "aperturas", "clics", "trafico", "engagement")},
         DIGITAL),
    Tipo("Capacitación / consulta", "Baja", (1, 3, 5, 10),
         ("capacitacion", "curso", "como uso", "como se usa", "explicar", "tutorial", "duda", "duda sobre", "consulta",
          "como se lee",
          "como interpreto"),
         {"Uso de un tablero": ("tablero", "como se lee", "como interpreto", "como uso"),
          "Power BI / DAX": ("dax", "power bi", "medida"),
          "Fuentes de datos": ("fuente", "iqvia", "close up", "adaptive")}),
    Tipo("Otro", PRIORIDAD_DEFECTO, (1, 3, 5, 10), (), {"Sin detalle": ()}),
)
POR_TIPO = {t.nombre: t for t in TIPOS}
TIPO_DEFECTO = "Otro"
SUBTIPOS = {t.nombre: tuple(t.subtipos) for t in TIPOS}


def sla_horas(tipo: str, prioridad: str) -> float:
    """Horas hábiles para resolver, según el tipo de ticket y la prioridad."""
    t = POR_TIPO.get(tipo, POR_TIPO[TIPO_DEFECTO])
    orden = POR_PRIORIDAD.get(prioridad, POR_PRIORIDAD[PRIORIDAD_DEFECTO]).orden
    return t.dias[orden - 1] * HORAS_DIA


#: Palabras que suben la prioridad, sin importar el tipo.
URGENCIA_CRITICA = ("urgente hoy", "para hoy", "critico", "bloqueante", "directorio hoy", "asap", "ya mismo")
URGENCIA_ALTA = ("urgente", "prioridad", "manana", "lo antes posible", "cuanto antes", "esta semana")


# ==========================================================================
# De quién: área solicitante y país
# ==========================================================================
AREAS = (
    "Marketing", "Fuerza de Ventas", "Gerencia de Filial", "Dirección Comercial", "Excelencia Comercial", "Digital",
    "Finanzas", "Medical Affairs", "Acceso al Mercado", "Business Development / Licencias", "Supply Chain",
    "IT", "Recursos Humanos", "Sin área",
)
AREA_DEFECTO = "Sin área"

PAISES = ("Uruguay (HQ)", "Argentina", "Bolivia", "Brasil", "Centroamérica", "Chile", "Colombia",
          "Ecuador", "México", "Paraguay", "Perú", "Venezuela", "Regional", "Sin país")
PAIS_DEFECTO = "Sin país"

CANALES = ("Correo", "Portal", "Manual", "Teams", "Teléfono")


# ==========================================================================
# Sobre qué: área terapéutica (por ATC), fuente de datos
# ==========================================================================
#: Área terapéutica por prefijo ATC: la definición del manual de Excelencia
#: Comercial (cap. 24.1), la misma de `AdiumAllinOne/.../reglas_adium.py`.
#: Gana el prefijo más largo («G03B» le gana a «G03»).
AREA_TERAPEUTICA_POR_ATC = {
    "G01": "Salud de la Mujer", "G02": "Salud de la Mujer", "G03": "Salud de la Mujer",
    "A11C2": "Salud de la Mujer", "M05B3": "Salud de la Mujer", "M05B9": "Salud de la Mujer",
    "G03B": "Salud del Hombre", "G04": "Salud del Hombre",
    "M": "Osteo Dolor", "N01": "Osteo Dolor", "N02": "Osteo Dolor",
    "C": "Cardiovascular", "B01": "Cardiovascular",
    "N03": "Neurociencias", "N04": "Neurociencias", "N05": "Neurociencias", "N06": "Neurociencias",
    "N07": "Neurociencias",
    "A08": "Metab & Obesidad", "A10": "Metab & Obesidad",
    "A01": "Aparato Digestivo", "A02": "Aparato Digestivo", "A03": "Aparato Digestivo", "A04": "Aparato Digestivo",
    "A05": "Aparato Digestivo", "A06": "Aparato Digestivo", "A07": "Aparato Digestivo", "A09": "Aparato Digestivo",
    "A16": "Aparato Digestivo",
    "L": "Oncología",
}
AREAS_TERAPEUTICAS = ("Metab & Obesidad", "Cardiovascular", "Aparato Digestivo", "Neurociencias", "Osteo Dolor",
                      "Salud de la Mujer", "Salud del Hombre", "Oncología", "Otra", "Transversal / no aplica")
AREA_TERAPEUTICA_DEFECTO = "Transversal / no aplica"


def area_terapeutica(atc: str) -> str | None:
    a = (atc or "").upper().replace(" ", "")
    mejor, largo = None, 0
    for prefijo, area in AREA_TERAPEUTICA_POR_ATC.items():
        if a.startswith(prefijo) and len(prefijo) > largo:
            mejor, largo = area, len(prefijo)
    return mejor


#: Unidad de negocio por prefijo ATC: la definición de la Planilla Maestra
#: (la misma de `reglas_adium.UNIDAD_NEGOCIO` en la suite). No es el área
#: terapéutica: la hipolipemiante (C10) es área Cardiovascular pero UN
#: «Gastro + Hipercol.», y la pregabalina (N03A) es Neurociencias por ATC
#: pero UN Osteo Dolor. Metabolismo (A08, A10) va a «Metab & Obesidad Lic»,
#: la única de metabolismo del manual; «Pr» se elige a mano cuando el
#: producto es propio.
UNIDAD_POR_ATC = {
    "B01": "Cardiovascular", "C01": "Cardiovascular", "C04": "Cardiovascular", "C05": "Cardiovascular",
    "C07": "Cardiovascular", "C08": "Cardiovascular", "C09": "Cardiovascular",
    "A01": "Gastro + Hipercol.", "A02": "Gastro + Hipercol.", "A03": "Gastro + Hipercol.", "A04": "Gastro + Hipercol.",
    "A05": "Gastro + Hipercol.", "A06": "Gastro + Hipercol.", "A07": "Gastro + Hipercol.", "A09": "Gastro + Hipercol.",
    "A16": "Gastro + Hipercol.", "C10": "Gastro + Hipercol.",
    "A08": "Metab & Obesidad Lic", "A10": "Metab & Obesidad Lic",
    "G04": "Salud del Hombre", "G03B": "Salud del Hombre",
    "G01": "Salud de la Mujer", "G02": "Salud de la Mujer", "G03": "Salud de la Mujer", "A11C2": "Salud de la Mujer",
    "M05B3": "Salud de la Mujer", "M05B9": "Salud de la Mujer",
    "M": "Osteo Dolor", "N01": "Osteo Dolor", "N02": "Osteo Dolor",
    "N03": "Neurociencias", "N04": "Neurociencias", "N05": "Neurociencias", "N06": "Neurociencias",
    "N07": "Neurociencias",
    "L": "Oncología",
}
UNIDADES_NEGOCIO = ("Cardiovascular", "Gastro + Hipercol.", "Metab & Obesidad Lic", "Metab & Obesidad Pr",
                    "Neurociencias", "Osteo Dolor", "Salud de la Mujer", "Salud del Hombre", "Oncología", "Otra",
                    "Transversal / no aplica")
UNIDAD_NEGOCIO_DEFECTO = "Transversal / no aplica"
_GABAPENTINOIDES = ("PREGABALIN", "GABAPENTIN")


def unidad_negocio(atc: str, mercado: str = "") -> str:
    """La UN de un ATC (y, para la N03A, de la molécula del mercado)."""
    a = (atc or "").upper().replace(" ", "")
    if not a:
        return UNIDAD_NEGOCIO_DEFECTO
    if a.startswith("N03A") and any(g in (mercado or "").upper() for g in _GABAPENTINOIDES):
        return "Osteo Dolor"
    mejor, largo = "Otra", 0
    for prefijo, un in UNIDAD_POR_ATC.items():
        if a.startswith(prefijo) and len(prefijo) > largo:
            mejor, largo = un, len(prefijo)
    return mejor


FUENTES = ("IQVIA", "Close Up", "Venta interna / Adaptive", "Stocking", "Non Retail", "MDW / Analysis Services",
           "Fabric", "Otra", "No aplica")
FUENTE_DEFECTO = "No aplica"
PALABRAS_FUENTE = {
    "IQVIA": ("iqvia", "pmb", "ddd", "siso", "share de mercado"),
    "Close Up": ("close up", "closeup", "recetas", "prescrip", "target"),
    "Venta interna / Adaptive": ("adaptive", "venta interna", "pea", "presupuesto"),
    "Stocking": ("stocking", "stock", "inventario"),
    "Non Retail": ("non retail", "institucional", "licitacion", "inefam"),
    "MDW / Analysis Services": ("mdw", "analysis services", "modern data", "cubo"),
    "Fabric": ("fabric", "lakehouse", "notebook"),
}

#: Resultados de la encuesta de conformidad.
CONFORME = "Conforme"
NO_CONFORME = "No conforme"
TACITA = "Tácita"
PENDIENTE = "Pendiente"
SIN_ENCUESTA = "Sin encuesta"
RESULTADOS_CONFORMIDAD = (CONFORME, NO_CONFORME, TACITA, PENDIENTE, SIN_ENCUESTA)
