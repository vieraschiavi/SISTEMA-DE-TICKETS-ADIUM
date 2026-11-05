"""
FreshService de IT ↔ la mesa.

En el portal de IT, «Incidencia en = Excelencia Comercial» es un pedido del
área que resuelve IT: no es nuestro. Para que alguien pueda pedirle algo a
Excelencia Comercial & Digital desde el portal que ya conoce, IT suma una
opción propia en ese desplegable (por defecto «Reportería Excelencia
Comercial», ver docs/PORTAL.md). Este módulo hace el resto:

1. `importar()` trae los tickets abiertos de esa opción por la API v2 de
   FreshService y los crea en la mesa (canal «FreshService»). Cada uno entra
   UNA vez: su id viaja como Message-ID (`<freshservice-1234@dominio>`) y
   pasa por el mismo candado que los correos, así que dos PCs del modo
   compartido no lo importan dos veces. En el ticket de FreshService queda
   una nota con nuestro número.
2. `devolver_estados()` le pasa a FreshService el estado de cada ticket
   (abierto, pendiente, resuelto, cerrado) y, al resolverlo, la resolución
   como nota pública. Lo que ya se devolvió queda anotado en el historial
   (evento «freshservice»), así no se repite.

Apagado por defecto (`freshservice_activo`), y la API key va SÓLO por
entorno (`TICKETS_FRESHSERVICE_CLAVE`). Biblioteca estándar.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from . import catalogos as C
from .correo import escapar, html_a_texto
from .servicio import ErrorMesa

#: Los estados de FreshService (API v2).
ABIERTO, PENDIENTE, RESUELTO, CERRADO = 2, 3, 4, 5
#: Nuestro estado → el de FreshService. «En espera del solicitante» es su «Pendiente».
A_FRESHSERVICE = {C.NUEVO: ABIERTO, C.ASIGNADO: ABIERTO, C.EN_CURSO: ABIERTO, C.REABIERTO: ABIERTO,
                  C.EN_ESPERA: PENDIENTE, C.RESUELTO: RESUELTO, C.CERRADO: CERRADO, C.CANCELADO: CERRADO}
NOMBRE_ESTADO = {ABIERTO: "Abierto", PENDIENTE: "Pendiente", RESUELTO: "Resuelto", CERRADO: "Cerrado"}
EVENTO = "freshservice"
#: La API de filtro devuelve de a 30. Diez páginas son 300 tickets abiertos de la opción de la
#: mesa a la vez: de sobra (lo que ya entró no vuelve a pedirse, porque se cierra o se resuelve).
POR_PAGINA, MAX_PAGINAS = 30, 10


class ErrorFreshService(ErrorMesa):
    """FreshService no respondió lo esperado, con el motivo en castellano."""


@dataclass
class Resultado:
    origen: str
    resultado: str
    numero: str | None = None


def origen(fs_id: int, dominio: str) -> str:
    return f"<freshservice-{int(fs_id)}@{dominio}>"


def id_de(message_id: str | None) -> int | None:
    m = re.match(r"<freshservice-(\d+)@", message_id or "")
    return int(m.group(1)) if m else None


def filtro(cfg) -> str:
    """La consulta del filtro: la opción de la mesa, sólo lo abierto o pendiente.

    `category` NO se puede filtrar por la API. «Incidencia en» es un campo propio del formulario
    de IT: se filtra por su nombre de API (`freshservice_campo`, el que devuelve
    `GET /api/v2/ticket_form_fields`), o por el grupo al que IT manda la opción
    (`freshservice_filtro = "group_id:1234"`)."""
    if cfg.freshservice_filtro:
        base = cfg.freshservice_filtro
    elif cfg.freshservice_campo:
        base = f"{cfg.freshservice_campo}:'{cfg.freshservice_valor.replace(chr(39), '')}'"
    else:
        raise ErrorFreshService("Falta freshservice_campo (el nombre de API del campo «Incidencia en») o "
                                "freshservice_filtro (p. ej. «group_id:1234»): ver docs/PORTAL.md.")
    return f"({base}) AND (status:{ABIERTO} OR status:{PENDIENTE})"


class ClienteFreshService:
    """La API v2 de FreshService con una API key (Basic, la clave como usuario y «X» como contraseña)."""

    def __init__(self, dominio: str, clave: str, abrir=urllib.request.urlopen):
        if not dominio:
            raise ErrorFreshService("Falta freshservice_dominio (p. ej. «empresa.freshservice.com»).")
        if not clave:
            raise ErrorFreshService("Falta la API key de FreshService en la variable TICKETS_FRESHSERVICE_CLAVE.")
        self.base = f"https://{dominio}/api/v2"
        self._auth = "Basic " + base64.b64encode(f"{clave}:X".encode()).decode()
        self.abrir = abrir

    def _pedir(self, metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo)
        req.add_header("Authorization", self._auth)
        req.add_header("Content-Type", "application/json")
        try:
            with self.abrir(req, timeout=30) as r:
                crudo = r.read()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300] if e.fp else ""
            motivos = {401: "la API key no vale", 403: "la cuenta de la API key no tiene permiso",
                       404: "no existe", 429: "límite de pedidos por minuto: se reintenta en la próxima vuelta"}
            raise ErrorFreshService(f"FreshService respondió {e.code} a {metodo} {ruta}: "
                                    f"{motivos.get(e.code, detalle)}") from e
        except urllib.error.URLError as e:
            raise ErrorFreshService(f"Sin conexión con FreshService ({e.reason}).") from e
        return json.loads(crudo) if crudo else {}

    def tickets(self, consulta: str) -> list[dict]:
        todos: list[dict] = []
        for pagina in range(1, MAX_PAGINAS + 1):
            q = urllib.parse.quote(f'"{consulta}"')
            lote = self._pedir("GET", f"/tickets/filter?query={q}&page={pagina}").get("tickets", [])
            todos += lote
            if len(lote) < POR_PAGINA:
                break
        return todos

    def persona(self, persona_id: int) -> tuple[str, str]:
        """(mail, nombre) del solicitante; si es un agente de IT, de su ficha de agente."""
        try:
            p = self._pedir("GET", f"/requesters/{persona_id}")["requester"]
            mail = p.get("primary_email")
        except ErrorFreshService as e:
            if " 404 " not in str(e):
                raise
            p = self._pedir("GET", f"/agents/{persona_id}")["agent"]
            mail = p.get("email")
        nombre = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x)
        return (mail or "").lower(), nombre

    def cambiar_estado(self, fs_id: int, estado: int) -> None:
        self._pedir("PUT", f"/tickets/{fs_id}", {"status": estado})

    def nota(self, fs_id: int, texto: str) -> None:
        cuerpo = "".join(f"<p>{escapar(linea)}</p>" for linea in texto.split("\n") if linea.strip())
        self._pedir("POST", f"/tickets/{fs_id}/notes", {"body": cuerpo, "private": False})


def _fecha(texto: str | None) -> datetime | None:
    if not texto:
        return None
    d = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d


def importar(mesa, cliente: ClienteFreshService, cfg) -> list[Resultado]:
    """Trae los tickets abiertos de la opción de la mesa. Uno que falla no frena a los demás."""
    resultados = []
    for fs in cliente.tickets(filtro(cfg)):
        clave = origen(fs["id"], cfg.freshservice_dominio)
        if mesa.db.correo_visto(clave):
            continue                                   # ya está: ni se anota
        try:
            mail, nombre = cliente.persona(fs["requester_id"])
            if not mail and fs.get("email"):
                mail = fs["email"].lower()
            descripcion = fs.get("description_text") or html_a_texto(fs.get("description") or "")
            r = mesa.crear_externo(clave, _fecha(fs.get("created_at")), fs.get("subject") or "(sin asunto)",
                                   f"{descripcion}\n\n(Entró por FreshService #{fs['id']})", mail, nombre,
                                   canal="FreshService", cc=[c.lower() for c in fs.get("cc_emails") or []])
            if r.numero:
                cliente.nota(fs["id"], f"Lo recibió {cfg.nombre_casilla} como {r.numero}. Las novedades llegan "
                                       "acá y por correo.")
                mesa.anotar(r.numero, EVENTO, f"estado {fs.get('status') or ABIERTO}")
            resultados.append(Resultado(clave, r.resultado, r.numero))
        except ErrorMesa as error:
            resultados.append(Resultado(clave, f"error: {error}"))
    return resultados


def _devuelto(mesa, t: dict) -> int | None:
    """El último estado que se le pasó a FreshService para este ticket."""
    for e in reversed(mesa.db.eventos(t["id"], EVENTO)):
        m = re.match(r"estado (\d)", e["detalle"] or "")
        if m:
            return int(m.group(1))
    return None


def devolver_estados(mesa, cliente: ClienteFreshService) -> list[Resultado]:
    """El estado de cada ticket que vino de FreshService, de vuelta allá (sólo lo que cambió)."""
    resultados = []
    for t in mesa.db.tickets("canal = ?", ("FreshService",)):
        fs_id = id_de(t["message_id"])
        quiero = A_FRESHSERVICE.get(t["estado"])
        if not fs_id or quiero is None or _devuelto(mesa, t) == quiero:
            continue
        try:
            # La resolución viaja una vez, como nota pública: al resolverlo (o al cerrarlo, si se
            # cerró sin que FreshService llegara a verlo resuelto) y al cancelarlo, con el motivo.
            if t["estado"] == C.CANCELADO:
                cliente.nota(fs_id, f"{t['numero']} · cancelado por el equipo.")
            elif quiero in (RESUELTO, CERRADO) and _devuelto(mesa, t) != RESUELTO and t["resolucion"]:
                cliente.nota(fs_id, f"{t['numero']} · resuelto: {t['resolucion']}")
            cliente.cambiar_estado(fs_id, quiero)
            mesa.anotar(t["numero"], EVENTO, f"estado {quiero} ({NOMBRE_ESTADO[quiero]})")
            resultados.append(Resultado(t["message_id"], f"estado → {NOMBRE_ESTADO[quiero]}", t["numero"]))
        except ErrorMesa as error:
            resultados.append(Resultado(t["message_id"], f"error: {error}", t["numero"]))
    return resultados


def sincronizar(mesa, cfg, abrir=urllib.request.urlopen) -> list[Resultado]:
    """Las dos cosas, si el conector está prendido y configurado. Sin conector, nada."""
    if not cfg.freshservice_activo:
        return []
    cliente = ClienteFreshService(cfg.freshservice_dominio, cfg.freshservice_clave, abrir)
    res = importar(mesa, cliente, cfg)
    if cfg.freshservice_devolver_estado:
        res += devolver_estados(mesa, cliente)
    return res
