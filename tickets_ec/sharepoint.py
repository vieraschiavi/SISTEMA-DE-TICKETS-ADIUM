"""
La mesa en Microsoft 365: las listas de SharePoint que usan Power Apps y
Power Automate, y su lectura para el tablero de Power BI.

Un solo esquema (`LISTAS`) para tres usos que no pueden desincronizarse:

1. `scripts/generar_powerplatform.py` escribe con él el script de PnP
   PowerShell que CREA las listas (columnas, tipos y opciones), las opciones
   salen de `catalogos.py`: el mismo «Tipo de ticket» en la app de Python, en
   Power Apps y en Power BI.
2. Power Apps y los flujos de Power Automate leen y escriben esas columnas
   por su nombre interno (sin espacios ni acentos: `AreaTerapeutica`).
3. `cargar()` lee las listas por Microsoft Graph y las vuelca en un
   `Almacen` en memoria con el mismo esquema que el de SQLite. Desde ahí,
   `exportar.tablas()` arma el modelo estrella IGUAL que con la base local:
   las horas hábiles, el reloj detenido y el SLA se calculan con el mismo
   código, sea cual sea el origen.

Permiso de Graph para leer: `Sites.Selected` sobre el sitio de la mesa (lo
otorga IT), con credenciales de aplicación. Sólo lectura.

4. El modo compartido (`compartida.py`) lee y ESCRIBE estas mismas listas con
   la cuenta de cada integrante: la app de Python en seis PCs, Power Apps y
   los flujos trabajan sobre los mismos ítems.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime

from . import catalogos as C
from .almacen import Almacen
from .correo import _pedir

#: (nombre interno, tipo SharePoint, opciones, columna en `Almacen`)
#: Tipos: Text, Note, Choice, Number, DateTime, Boolean.
LISTAS: dict[str, list[tuple]] = {
    "Tickets": [
        ("Title", "Text", None, "asunto"),
        ("Numero", "Text", None, "numero"),
        ("Descripcion", "Note", None, "descripcion"),
        ("SolicitanteMail", "Text", None, "solicitante_mail"),
        ("SolicitanteNombre", "Text", None, "solicitante_nombre"),
        ("Area", "Choice", C.AREAS, "area"),
        ("Pais", "Choice", C.PAISES, "pais"),
        ("Equipo", "Choice", C.EQUIPOS, "equipo"),
        ("Tipo", "Choice", tuple(t.nombre for t in C.TIPOS), "tipo"),
        ("Subtipo", "Text", None, "subtipo"),
        ("Prioridad", "Choice", tuple(p.nombre for p in C.PRIORIDADES), "prioridad"),
        ("Canal", "Choice", C.CANALES, "canal"),
        ("Estado", "Choice", C.ESTADOS, "estado"),
        ("Subestado", "Text", None, "subestado"),
        ("AnalistaMail", "Text", None, "analista_mail"),
        ("ATC", "Text", None, "atc"),
        ("AreaTerapeutica", "Choice", C.AREAS_TERAPEUTICAS, "area_terapeutica"),
        ("UnidadNegocio", "Choice", C.UNIDADES_NEGOCIO, "unidad_negocio"),
        ("Mercado", "Text", None, "mercado"),
        ("FuenteDatos", "Choice", C.FUENTES, "fuente_datos"),
        ("Tablero", "Text", None, "tablero"),
        ("Cc", "Text", None, "cc"),
        ("Clasificacion", "Note", None, "clasificacion"),
        ("MessageId", "Text", None, "message_id"),
        ("CreadoEn", "DateTime", None, "creado_en"),
        ("ActualizadoEn", "DateTime", None, "actualizado_en"),
        ("AsignadoEn", "DateTime", None, "asignado_en"),
        ("PrimeraRespuestaEn", "DateTime", None, "primera_respuesta_en"),
        ("EnCursoEn", "DateTime", None, "en_curso_en"),
        ("ResueltoEn", "DateTime", None, "resuelto_en"),
        ("CerradoEn", "DateTime", None, "cerrado_en"),
        ("CanceladoEn", "DateTime", None, "cancelado_en"),
        ("Reaperturas", "Number", None, "reaperturas"),
        ("VecesEnEspera", "Number", None, "veces_en_espera"),
        ("Conformidad", "Choice", C.RESULTADOS_CONFORMIDAD, "conformidad"),
        ("CSAT", "Number", None, "csat"),
        ("Resolucion", "Note", None, "resolucion"),
        # Lo calculan la app y los flujos para mostrar el semáforo; el tablero
        # no lo lee: recalcula el SLA con el reloj detenido (ver sla.py).
        ("VenceEn", "DateTime", None, None),
    ],
    "Eventos": [
        ("Title", "Text", None, "tipo"),
        ("TicketNumero", "Text", None, "_numero"),
        ("En", "DateTime", None, "en"),
        ("Usuario", "Text", None, "usuario"),
        ("EstadoDesde", "Choice", C.ESTADOS, "estado_desde"),
        ("EstadoHasta", "Choice", C.ESTADOS, "estado_hasta"),
        ("Publico", "Boolean", None, "publico"),
        ("Detalle", "Note", None, "detalle"),
    ],
    "Encuestas": [
        ("Title", "Text", None, "_numero"),
        ("Ronda", "Number", None, "ronda"),
        ("EnviadaEn", "DateTime", None, "enviada_en"),
        ("RespondidaEn", "DateTime", None, "respondida_en"),
        ("Resultado", "Choice", (C.PENDIENTE, C.CONFORME, C.NO_CONFORME, C.TACITA), "resultado"),
        ("CSAT", "Number", None, "csat"),
        ("Comentario", "Note", None, "comentario"),
        # sha256 del token del link: con él cualquier PC del equipo valida una
        # respuesta. Nunca el token en sí.
        ("TokenHash", "Text", None, "token_hash"),
    ],
    "Personas": [
        ("Title", "Text", None, "nombre"),
        ("Mail", "Text", None, "mail"),
        ("Area", "Choice", C.AREAS, "area"),
        ("Pais", "Choice", C.PAISES, "pais"),
        ("Rol", "Choice", ("solicitante", "analista", "coordinador"), "rol"),
        ("Activo", "Boolean", None, "activo"),
    ],
    # Un ítem por correo de la casilla: es el candado de la ingesta. La PC
    # que crea el ítem (Title = Message-ID, con valores únicos) procesa el
    # correo; la que llega segunda recibe un 409 y lo saltea.
    "Correos": [
        ("Title", "Text", None, "message_id"),
        ("TicketNumero", "Text", None, "_numero"),
        ("RecibidoEn", "DateTime", None, "recibido_en"),
        ("Remitente", "Text", None, "remitente"),
        ("Asunto", "Text", None, "asunto"),
        ("Resultado", "Text", None, "resultado"),
    ],
    # Las que siguen las usan los flujos y la app; Power BI no las lee.
    "ReglasClasificacion": [
        ("Title", "Text", None, None),          # la palabra, sin acentos y en minúscula
        ("Tipo", "Choice", tuple(t.nombre for t in C.TIPOS), None),
        ("Peso", "Number", None, None),
        ("Equipo", "Choice", C.EQUIPOS, None),
    ],
    "Mercados": [
        ("Title", "Text", None, None),
        ("AreaTerapeutica", "Text", None, None),
        ("UnidadNegocio", "Text", None, None),
        ("ATC", "Text", None, None),
        ("CTs", "Text", None, None),
    ],
    "Feriados": [
        ("Title", "Text", None, None),
        ("Fecha", "DateTime", None, None),
    ],
    "Subtipos": [
        ("Title", "Text", None, None),
        ("Tipo", "Choice", tuple(t.nombre for t in C.TIPOS), None),
    ],
    "SLA": [
        ("Title", "Text", None, None),          # el tipo de ticket
        ("Prioridad", "Choice", tuple(p.nombre for p in C.PRIORIDADES), None),
        ("DiasResolucion", "Number", None, None),
        ("HorasRespuesta", "Number", None, None),
        ("Equipo", "Choice", C.EQUIPOS, None),
    ],
}

#: El nombre que ve la persona en SharePoint y en Power Apps.
VISIBLES = {"Title": "Asunto", "Numero": "Número", "Descripcion": "Descripción", "SolicitanteMail": "Mail solicitante",
            "SolicitanteNombre": "Solicitante", "Area": "Área solicitante", "Pais": "País", "Equipo": "Equipo resolutor",
            "Tipo": "Tipo de ticket", "AnalistaMail": "Analista (mail)", "AreaTerapeutica": "Área terapéutica", "UnidadNegocio": "Unidad de negocio",
            "FuenteDatos": "Fuente de datos", "Clasificacion": "Clasificación", "CreadoEn": "Creado",
            "ActualizadoEn": "Actualizado", "AsignadoEn": "Asignado", "PrimeraRespuestaEn": "Primera respuesta",
            "EnCursoEn": "En curso", "ResueltoEn": "Resuelto", "CerradoEn": "Cerrado", "CanceladoEn": "Cancelado",
            "VecesEnEspera": "Veces en espera", "Resolucion": "Resolución", "VenceEn": "Vence", "TicketNumero": "Ticket",
            "EstadoDesde": "Estado desde", "EstadoHasta": "Estado hasta", "Publico": "Público",
            "EnviadaEn": "Enviada", "RespondidaEn": "Respondida", "DiasResolucion": "Días de resolución",
            "HorasRespuesta": "Horas a la primera respuesta", "CTs": "Clases terapéuticas",
            "TokenHash": "Hash del link", "RecibidoEn": "Recibido"}
#: El nombre visible de `Title` en cada lista.
TITULOS = {"Tickets": "Asunto", "Eventos": "Tipo de evento", "Encuestas": "Ticket", "Personas": "Nombre",
           "Correos": "Message-ID",
           "ReglasClasificacion": "Palabra", "Mercados": "Mercado", "Feriados": "Feriado", "Subtipos": "Subtipo",
           "SLA": "Tipo de ticket"}
#: Las columnas por las que filtran la app y los flujos: indexadas, para
#: que una lista de más de 5.000 ítems siga respondiendo. `Modified` es la
#: de la sincronización del modo compartido («lo que cambió desde las 10:42»).
INDEXADAS = {"Tickets": ("Numero", "Estado", "SolicitanteMail", "AnalistaMail", "Equipo", "CreadoEn", "Modified"),
             "Eventos": ("TicketNumero", "Modified"), "Encuestas": ("Title", "Modified"),
             "Personas": ("Mail", "Modified"), "Correos": ("Title",)}
#: Columnas con valores únicos (SharePoint las exige indexadas).
UNICAS = {"Correos": ("Title",)}


class ClienteGraph:
    """Credenciales de aplicación contra Microsoft Graph, sólo lectura."""

    BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, tenant: str, cliente: str, secreto: str, abrir=urllib.request.urlopen):
        if not (tenant and cliente and secreto):
            raise ValueError("Graph necesita tenant, cliente y secreto (TICKETS_GRAPH_SECRETO).")
        self.tenant, self.cliente, self.secreto, self.abrir = tenant, cliente, secreto, abrir
        self._token = ""

    def token(self) -> str:
        if not self._token:
            cuerpo = urllib.parse.urlencode({
                "client_id": self.cliente, "client_secret": self.secreto, "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default"}).encode()
            r = _pedir(f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token", metodo="POST",
                       datos=cuerpo, tipo="application/x-www-form-urlencoded", abrir=self.abrir)
            self._token = json.loads(r)["access_token"]
        return self._token

    def todos(self, url: str) -> list[dict]:
        """Sigue `@odata.nextLink` hasta el final (Graph pagina de a 200)."""
        filas = []
        while url:
            r = json.loads(_pedir(url, token=self.token(), abrir=self.abrir))
            filas += r.get("value", [])
            url = r.get("@odata.nextLink", "")
        return filas

    def sitio(self, host: str, ruta: str) -> str:
        """`adium.sharepoint.com`, `/sites/TicketsEC` → el id del sitio."""
        r = json.loads(_pedir(f"{self.BASE}/sites/{host}:{ruta}", token=self.token(), abrir=self.abrir))
        return r["id"]

    def items(self, sitio: str, lista: str) -> list[dict]:
        url = f"{self.BASE}/sites/{sitio}/lists/{urllib.parse.quote(lista)}/items?expand=fields&$top=200"
        return [i.get("fields", {}) for i in self.todos(url)]


class ClienteCarpeta:
    """Las listas exportadas a CSV por el flujo 6 (una por lista, con los
    nombres internos de columna como encabezado). Es el camino sin app de
    Entra ID: Power Automate deja los CSV en una biblioteca sincronizada y el
    export diario los lee de la carpeta local."""

    def __init__(self, carpeta):
        from pathlib import Path
        self.carpeta = Path(carpeta)

    def items(self, _sitio: str, lista: str) -> list[dict]:
        import csv
        ruta = self.carpeta / f"{lista}.csv"
        if not ruta.is_file():
            return []
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            return [{k: (v if v != "" else None) for k, v in fila.items()} for fila in csv.DictReader(f)]


def _valor(tipo: str, v):
    if v in (None, ""):
        return None
    if tipo == "DateTime":
        # Graph devuelve UTC («2026-10-21T12:00:00Z»); la mesa trabaja en hora local.
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.astimezone().replace(tzinfo=None) if d.tzinfo else d
    if tipo == "Number":
        return int(v) if float(v).is_integer() else float(v)
    if tipo == "Boolean":
        return int(str(v).strip().lower() in ("1", "true", "sí", "si", "yes")) if isinstance(v, str) else int(bool(v))
    return v


def cargar(cliente: ClienteGraph | ClienteCarpeta, sitio: str = "") -> Almacen:
    """Las listas de la mesa → un `Almacen` en memoria, listo para `exportar.tablas()`."""
    db = Almacen(":memory:")
    with db.transaccion():
        for f in cliente.items(sitio, "Personas"):
            fila = {col: _valor(t, f.get(interno)) for interno, t, _o, col in LISTAS["Personas"] if col}
            if fila.get("mail"):
                db.guardar_persona(fila["mail"], fila.get("nombre") or fila["mail"], fila.get("area"),
                                   fila.get("pais"), fila.get("rol") or "solicitante", bool(fila.get("activo", 1)))
        ids: dict[str, int] = {}
        for f in sorted(cliente.items(sitio, "Tickets"), key=lambda f: f.get("CreadoEn") or ""):
            fila = {col: _valor(t, f.get(interno)) for interno, t, _o, col in LISTAS["Tickets"] if col}
            if not fila.get("numero") or not fila.get("creado_en"):
                continue
            fila.setdefault("actualizado_en", fila["creado_en"])
            fila["actualizado_en"] = fila["actualizado_en"] or fila["creado_en"]
            fila["reaperturas"] = fila.get("reaperturas") or 0
            fila["veces_en_espera"] = fila.get("veces_en_espera") or 0
            fila["conformidad"] = fila.get("conformidad") or C.SIN_ENCUESTA
            numero = fila.pop("numero")
            db._validar_columnas(fila)
            cur = db._ejecutar(
                f"INSERT INTO tickets({', '.join(fila)}, numero) VALUES ({', '.join('?' for _ in fila)}, ?)",
                [v.replace(microsecond=0).isoformat() if isinstance(v, datetime) else v for v in fila.values()]
                + [numero])
            ids[numero] = cur.lastrowid
        for f in cliente.items(sitio, "Eventos"):
            fila = {col: _valor(t, f.get(interno)) for interno, t, _o, col in LISTAS["Eventos"] if col}
            tid = ids.get(fila.pop("_numero") or "")
            if tid and fila.get("en"):
                db.agregar_evento(tid, fila["en"], fila.get("usuario") or "", fila.get("tipo") or "estado",
                                  estado_desde=fila.get("estado_desde"), estado_hasta=fila.get("estado_hasta"),
                                  publico=bool(fila.get("publico")), detalle=fila.get("detalle") or "")
        for i, f in enumerate(cliente.items(sitio, "Encuestas")):
            fila = {col: _valor(t, f.get(interno)) for interno, t, _o, col in LISTAS["Encuestas"] if col}
            tid = ids.get(fila.pop("_numero") or "")
            if tid and fila.get("enviada_en"):
                token_hash = fila.get("token_hash") or f"sharepoint-{i}"
                db.agregar_encuesta(tid, int(fila.get("ronda") or 1), token_hash, fila["enviada_en"])
                e = db.consulta("SELECT id FROM encuestas WHERE token_hash = ?", (token_hash,))[0]
                if fila.get("resultado") and fila["resultado"] != C.PENDIENTE:
                    db.responder_encuesta(e["id"], fila.get("respondida_en") or fila["enviada_en"],
                                          fila["resultado"], fila.get("csat"), fila.get("comentario") or "")
    return db
