"""
El modo compartido: seis PCs, una sola mesa.

Cada integrante abre la app (o la suite Adium All in One) en SU PC y entra
con su cuenta de Microsoft de Adium. Ninguna PC es «la base»: la base son
las listas de SharePoint de `sharepoint.LISTAS`, las mismas que usan Power
Apps y los flujos. La casilla las alimenta: el correo que entra se vuelve
ticket en la lista, y cada PC lo ve en la siguiente sincronización.

Cómo se reparte el trabajo sin pisarse:

* **Lectura.** Cada PC tiene una copia local en SQLite (`AlmacenCompartido`
  hereda de `Almacen`), así la bandeja, los indicadores y el export a Power
  BI corren igual que en modo local. `sincronizar()` trae lo que cambió en
  las listas desde la última vez (`Modified`, indexada).
* **Escritura.** Cada cambio de un ticket se escribe PRIMERO en la lista,
  con el `eTag` que esa PC leyó (`If-Match`). Si otro integrante lo cambió
  en el medio, SharePoint responde 412 y la operación entera se cae con
  `Conflicto`: nada se pisa en silencio. La PC se marca desactualizada y la
  próxima pantalla trae la versión nueva.
* **Eventos.** Son sólo agregados (nadie edita uno ajeno): se guardan en la
  copia local y en una cola (`sp_pendientes`) que se sube al confirmar la
  operación. Si en ese momento no hay red, quedan en la cola y suben en la
  próxima sincronización. Un evento no se pierde ni se duplica.
* **Casilla.** Dos PCs que leen el mismo correo no lo duplican: antes de
  procesarlo, cada una crea su ítem en la lista `Correos` con el Message-ID
  como título de valores únicos. La primera gana; la segunda recibe 409 y
  lo saltea.
* **Números.** `EC-00042` sale del id del ítem de la lista, como en el
  flujo 1 de Power Automate: no hay dos PCs que puedan dar el mismo número.

Nada de esto guarda una contraseña: el token lo da Microsoft a la cuenta de
cada persona (`acceso.py`) y vive en memoria mientras la app está abierta.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from . import catalogos as C
from .almacen import Almacen, iso
from .servicio import ErrorMesa
from .sharepoint import LISTAS, _valor


class ErrorListas(ErrorMesa):
    """SharePoint no respondió lo esperado (red, permisos, una columna que falta)."""


class Conflicto(ErrorMesa):
    """Otro integrante cambió el mismo ítem después de que esta PC lo leyó."""


class Duplicado(ErrorMesa):
    """Un valor que la lista exige único ya existe (el candado de la casilla)."""


#: Un margen para los relojes: se pide «lo cambiado desde la última vez,
#: menos dos minutos». Traer de más no rompe nada (es un upsert).
SOLAPE = timedelta(minutes=2)
#: SharePoint corta las columnas de texto de una línea en 255 caracteres.
MAX_TEXTO = 255


# ==========================================================================
# De una fila de la mesa a los campos de una lista, y vuelta
# ==========================================================================
def _a_graph(tipo: str, v):
    if v is None:
        return None
    if tipo == "DateTime":
        v = datetime.fromisoformat(v) if isinstance(v, str) else v
        # La mesa trabaja en hora local sin zona; SharePoint guarda UTC.
        return v.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if tipo == "Boolean":
        return bool(v)
    if tipo == "Text":
        return str(v)[:MAX_TEXTO]
    return v


def a_graph(lista: str, fila: dict) -> dict:
    """Las columnas de `fila` (nombres de la mesa) con el nombre interno de la lista."""
    return {interno: _a_graph(tipo, fila[col]) for interno, tipo, _o, col in LISTAS[lista]
            if col and col in fila}


def de_graph(lista: str, campos: dict) -> dict:
    return {col: _valor(tipo, campos.get(interno)) for interno, tipo, _o, col in LISTAS[lista] if col}


# ==========================================================================
# El cliente de las listas (Microsoft Graph con la cuenta de la persona)
# ==========================================================================
class ListasGraph:
    """Lee y escribe las listas del sitio de la mesa por Microsoft Graph.

    `token` es una función: el de `acceso.Sesion.token`, que lo renueva solo.
    Permiso delegado: `Sites.ReadWrite.All` (la persona sólo puede lo que ya
    puede en el sitio: si no tiene edición, Graph responde 403)."""

    BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, host: str, ruta: str, token, abrir=urllib.request.urlopen):
        if not host:
            raise ErrorListas("Falta sharepoint_host (p. ej. «adium.sharepoint.com») en config.equipo.toml.")
        self.host, self.ruta, self._token, self.abrir = host, ruta, token, abrir
        self._sitio = ""

    def _pedir(self, metodo: str, url: str, cuerpo: dict | None = None, si_coincide: str | None = None) -> dict:
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, method=metodo)
        req.add_header("Authorization", f"Bearer {self._token()}")
        req.add_header("Accept", "application/json")
        # Sin esto Graph rechaza un $filter sobre una columna que no sea Title.
        req.add_header("Prefer", "HonorNonIndexedQueriesWarningMayFailRandomly")
        if datos is not None:
            req.add_header("Content-Type", "application/json")
        if si_coincide:
            req.add_header("If-Match", si_coincide)
        try:
            with self.abrir(req, timeout=30) as r:
                crudo = r.read()
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300] if e.fp else ""
            if e.code == 412:
                raise Conflicto("Otro integrante cambió este ticket mientras lo tenías abierto. Ya se trae la "
                                "versión nueva: revisala y volvé a intentar.") from e
            if e.code == 409 or (e.code == 400 and "duplica" in detalle.lower()):
                raise Duplicado(detalle or "Valor duplicado") from e
            if e.code in (401, 403):
                raise ErrorListas(f"SharePoint no te deja ({e.code}): tu cuenta necesita edición en el sitio de "
                                  "la mesa (lo da el dueño del sitio).") from e
            raise ErrorListas(f"SharePoint respondió {e.code} a {metodo}: {detalle}") from e
        except urllib.error.URLError as e:
            raise ErrorListas(f"Sin conexión con SharePoint ({e.reason}). Lo que hiciste queda en la cola y "
                              "sube solo cuando vuelva la red.") from e
        return json.loads(crudo) if crudo else {}

    def sitio(self) -> str:
        if not self._sitio:
            self._sitio = self._pedir("GET", f"{self.BASE}/sites/{self.host}:{self.ruta}")["id"]
        return self._sitio

    def _url(self, lista: str, resto: str = "") -> str:
        return f"{self.BASE}/sites/{self.sitio()}/lists/{urllib.parse.quote(lista)}/items{resto}"

    @staticmethod
    def _item(i: dict) -> dict:
        return {"id": int(i["id"]), "etag": i.get("eTag") or i.get("fields", {}).get("@odata.etag", ""),
                "fields": i.get("fields", {})}

    def _todos(self, url: str) -> list[dict]:
        filas = []
        while url:
            r = self._pedir("GET", url)
            filas += [self._item(i) for i in r.get("value", [])]
            url = r.get("@odata.nextLink", "")
        return filas

    def items(self, lista: str, desde: datetime | None = None) -> list[dict]:
        """Los ítems de la lista (todos, o los modificados desde `desde`, UTC)."""
        filtro = ""
        if desde:
            cuando = desde.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            filtro = "&$filter=" + urllib.parse.quote(f"fields/Modified ge '{cuando}'")
        return self._todos(self._url(lista, f"?expand=fields&$top=200{filtro}"))

    def buscar(self, lista: str, campo: str, valor: str) -> list[dict]:
        filtro = urllib.parse.quote(f"fields/{campo} eq '{str(valor).replace(chr(39), chr(39) * 2)}'")
        return self._todos(self._url(lista, f"?expand=fields&$filter={filtro}"))

    def crear(self, lista: str, campos: dict) -> tuple[int, str]:
        r = self._pedir("POST", self._url(lista), {"fields": campos})
        return int(r["id"]), r.get("eTag", "")

    def actualizar(self, lista: str, item_id: int, campos: dict, etag: str | None = None) -> str:
        """El eTag nuevo. Con `etag`, SharePoint rechaza (412 → `Conflicto`) si alguien cambió el ítem."""
        r = self._pedir("PATCH", self._url(lista, f"/{item_id}/fields"), campos, si_coincide=etag or "*")
        return r.get("@odata.etag", "")

    def borrar(self, lista: str, item_id: int) -> None:
        self._pedir("DELETE", self._url(lista, f"/{item_id}"))


# ==========================================================================
# La copia local que escribe primero en las listas
# ==========================================================================
_EXTRA = """
CREATE TABLE IF NOT EXISTS sp_items (
    lista  TEXT NOT NULL,
    clave  TEXT NOT NULL,          -- el id del ticket/encuesta, el mail de la persona o el Message-ID
    id     INTEGER NOT NULL,       -- el id del ítem en la lista
    etag   TEXT,
    PRIMARY KEY (lista, clave)
);
CREATE TABLE IF NOT EXISTS sp_pendientes (
    orden     INTEGER PRIMARY KEY AUTOINCREMENT,
    lista     TEXT NOT NULL,
    local_id  INTEGER,             -- el id provisorio (negativo) del evento en la copia local
    campos    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sp_estado (clave TEXT PRIMARY KEY, valor TEXT);
"""


class AlmacenCompartido(Almacen):
    """Un `Almacen` cuya fuente de verdad son las listas de SharePoint.

    `Mesa` no se entera: llama a los mismos métodos que en modo local. Lo que
    cambia es que cada escritura va primero a la lista (y puede fallar con
    `Conflicto`), y que `sincronizar()` trae lo que hicieron los demás."""

    def __init__(self, ruta, listas, reloj=None):
        super().__init__(ruta)
        self._con.executescript(_EXTRA)
        self.listas = listas
        self.reloj = reloj or (lambda: datetime.now(UTC))
        #: True cuando una escritura chocó con la de otro: hay que sincronizar.
        self.desactualizado = False
        #: El último error al subir la cola (sin red, sin permiso), para mostrarlo.
        self.error_subida = ""

    # ---- las marcas de cada ítem ------------------------------------------
    def _item(self, lista: str, clave) -> tuple[int, str] | None:
        f = self.consulta("SELECT id, etag FROM sp_items WHERE lista = ? AND clave = ?", (lista, str(clave)))
        return (f[0]["id"], f[0]["etag"]) if f else None

    def _anotar(self, lista: str, clave, item_id: int, etag: str) -> None:
        self._ejecutar("INSERT INTO sp_items(lista, clave, id, etag) VALUES (?,?,?,?) ON CONFLICT(lista, clave) "
                       "DO UPDATE SET id = excluded.id, etag = excluded.etag", (lista, str(clave), item_id, etag))

    def _numero(self, ticket_id: int) -> str:
        return self.consulta("SELECT numero FROM tickets WHERE id = ?", (ticket_id,))[0]["numero"]

    @property
    def pendientes(self) -> int:
        return self.consulta("SELECT COUNT(*) AS n FROM sp_pendientes")[0]["n"]

    @property
    def ultima_sincronizacion(self) -> datetime | None:
        f = self.consulta("SELECT valor FROM sp_estado WHERE clave = 'ultima'")
        return datetime.fromisoformat(f[0]["valor"]) if f else None

    # ---- transacciones: la cola sube al confirmar ---------------------------
    @contextmanager
    def transaccion(self):
        afuera = not self._en_transaccion
        with super().transaccion():
            yield self
        if afuera:
            self.subir_pendientes()

    def subir_pendientes(self) -> int:
        """Sube la cola en orden. Se frena en el primer error (queda para la próxima)."""
        subidos = 0
        for p in self.consulta("SELECT * FROM sp_pendientes ORDER BY orden"):
            try:
                item_id, etag = self.listas.crear(p["lista"], json.loads(p["campos"]))
            except ErrorMesa as error:
                self.error_subida = str(error)
                return subidos
            with Almacen.transaccion(self):
                self._ejecutar("DELETE FROM sp_pendientes WHERE orden = ?", (p["orden"],))
                if p["local_id"] is not None:
                    self._ejecutar("UPDATE eventos SET id = ? WHERE id = ?", (item_id, p["local_id"]))
            subidos += 1
        self.error_subida = ""
        return subidos

    # ---- tickets --------------------------------------------------------
    def insertar_ticket(self, prefijo: str, **campos) -> dict:
        self._validar_columnas(campos)
        item_id, etag = self.listas.crear("Tickets", a_graph("Tickets", campos))
        numero = f"{prefijo}-{item_id:05d}"          # el mismo número que da el flujo 1
        etag = self.listas.actualizar("Tickets", item_id, {"Numero": numero}, etag) or etag
        columnas = ["id", "numero", *campos]
        valores = [item_id, numero, *(iso(v) if isinstance(v, datetime) else v for v in campos.values())]
        self._ejecutar(f"INSERT INTO tickets({', '.join(columnas)}) VALUES ({', '.join('?' for _ in columnas)})",
                       valores)
        self._anotar("Tickets", item_id, item_id, etag)
        return self.ticket(numero)

    def actualizar_ticket(self, ticket_id: int, **campos) -> None:
        if not campos:
            return
        self._validar_columnas(campos)
        marca = self._item("Tickets", ticket_id)
        try:
            etag = self.listas.actualizar("Tickets", ticket_id, a_graph("Tickets", campos), marca[1] if marca else None)
        except Conflicto:
            self.desactualizado = True
            raise
        super().actualizar_ticket(ticket_id, **campos)
        self._anotar("Tickets", ticket_id, ticket_id, etag)

    # ---- eventos: a la cola ------------------------------------------------
    def agregar_evento(self, ticket_id: int, en: datetime, usuario: str, tipo: str, *,
                       estado_desde: str | None = None, estado_hasta: str | None = None,
                       publico: bool = False, detalle: str = "") -> None:
        provisorio = min(-1, (self.consulta("SELECT MIN(id) AS m FROM eventos")[0]["m"] or 0) - 1)
        self._ejecutar(
            "INSERT INTO eventos(id, ticket_id, en, usuario, tipo, estado_desde, estado_hasta, publico, detalle) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (provisorio, ticket_id, iso(en), usuario, tipo, estado_desde, estado_hasta, int(publico), detalle))
        campos = a_graph("Eventos", {"tipo": tipo, "_numero": self._numero(ticket_id), "en": en, "usuario": usuario,
                                     "estado_desde": estado_desde, "estado_hasta": estado_hasta,
                                     "publico": bool(publico), "detalle": detalle})
        self._ejecutar("INSERT INTO sp_pendientes(lista, local_id, campos) VALUES ('Eventos', ?, ?)",
                       (provisorio, json.dumps(campos, ensure_ascii=False)))
        if not self._en_transaccion:
            self.subir_pendientes()

    # ---- encuestas ----------------------------------------------------
    def agregar_encuesta(self, ticket_id: int, ronda: int, token_hash: str, enviada_en: datetime) -> None:
        item_id, etag = self.listas.crear("Encuestas", a_graph("Encuestas", {
            "_numero": self._numero(ticket_id), "ronda": ronda, "enviada_en": enviada_en,
            "resultado": C.PENDIENTE, "token_hash": token_hash}))
        self._ejecutar("INSERT INTO encuestas(id, ticket_id, ronda, token_hash, enviada_en) VALUES (?,?,?,?,?)",
                       (item_id, ticket_id, ronda, token_hash, iso(enviada_en)))
        self._anotar("Encuestas", item_id, item_id, etag)

    def responder_encuesta(self, encuesta_id: int, en: datetime, resultado: str, csat: int | None,
                           comentario: str) -> None:
        etag = self.listas.actualizar("Encuestas", encuesta_id, a_graph("Encuestas", {
            "respondida_en": en, "resultado": resultado, "csat": csat, "comentario": comentario}))
        super().responder_encuesta(encuesta_id, en, resultado, csat, comentario)
        self._anotar("Encuestas", encuesta_id, encuesta_id, etag)

    # ---- personas -----------------------------------------------------
    def guardar_persona(self, mail: str, nombre: str, area: str | None = None, pais: str | None = None,
                        rol: str = "solicitante", activo: bool = True) -> None:
        mail = mail.lower()
        previa = self.persona(mail)
        igual = previa and (previa["nombre"], previa["rol"], bool(previa["activo"])) == (nombre, rol, bool(activo)) \
            and area in (None, previa["area"]) and pais in (None, previa["pais"])
        if not igual:     # el solicitante de siempre no le cuesta una escritura a cada ticket
            campos = {"nombre": nombre, "mail": mail, "rol": rol, "activo": bool(activo)}
            campos.update({k: v for k, v in (("area", area), ("pais", pais)) if v})
            marca = self._item("Personas", mail)
            if not marca:
                hallada = self.listas.buscar("Personas", "Mail", mail)
                marca = (hallada[0]["id"], hallada[0]["etag"]) if hallada else None
            if marca:
                item_id, etag = marca[0], self.listas.actualizar("Personas", marca[0], a_graph("Personas", campos))
            else:
                item_id, etag = self.listas.crear("Personas", a_graph("Personas", campos))
            self._anotar("Personas", mail, item_id, etag)
        super().guardar_persona(mail, nombre, area, pais, rol, activo)

    # ---- la casilla: el candado ---------------------------------------------
    def reclamar_correo(self, message_id: str) -> bool:
        if self.correo_visto(message_id):
            return False
        try:
            item_id, etag = self.listas.crear("Correos", a_graph("Correos", {
                "message_id": message_id, "resultado": "procesando"}))
        except Duplicado:
            return False                  # otra PC lo está procesando o ya lo procesó
        self._anotar("Correos", message_id, item_id, etag)
        return True

    def soltar_correo(self, message_id: str) -> None:
        marca = self._item("Correos", message_id)
        if not marca:
            return
        try:
            self.listas.borrar("Correos", marca[0])
        except ErrorMesa:
            pass                          # queda «procesando»: lo ve quien revise la lista
        self._ejecutar("DELETE FROM sp_items WHERE lista = 'Correos' AND clave = ?", (message_id,))

    def registrar_correo(self, message_id: str, ticket_id: int | None, recibido_en: datetime,
                         remitente: str, asunto: str, resultado: str) -> None:
        campos = a_graph("Correos", {"message_id": message_id, "_numero": self._numero(ticket_id) if ticket_id else None,
                                     "recibido_en": recibido_en, "remitente": remitente, "asunto": asunto or "",
                                     "resultado": resultado})
        marca = self._item("Correos", message_id)
        try:
            if marca:
                self.listas.actualizar("Correos", marca[0], campos)
            else:
                self.listas.crear("Correos", campos)
        except Duplicado:
            pass
        super().registrar_correo(message_id, ticket_id, recibido_en, remitente, asunto, resultado)

    # ---- traer lo de los demás ----------------------------------------------
    def sincronizar(self, completa: bool = False) -> dict[str, int]:
        """Sube la cola y trae lo modificado en las listas desde la última vez.
        `completa=True` trae todo (la primera vez, o para rehacer la copia)."""
        self.subir_pendientes()
        inicio = self.reloj()
        ultima = None if completa else self.ultima_sincronizacion
        desde = ultima - SOLAPE if ultima else None
        traidos = {lista: self.listas.items(lista, desde) for lista in ("Personas", "Tickets", "Encuestas", "Eventos")}
        with Almacen.transaccion(self):
            for i in traidos["Personas"]:
                f = de_graph("Personas", i["fields"])
                if f.get("mail"):
                    Almacen.guardar_persona(self, f["mail"], f.get("nombre") or f["mail"], f.get("area"),
                                            f.get("pais"), f.get("rol") or "solicitante",
                                            bool(1 if f.get("activo") is None else f["activo"]))
                    self._anotar("Personas", f["mail"].lower(), i["id"], i["etag"])
            for i in traidos["Tickets"]:
                self._traer_ticket(i)
            ids = {t["numero"]: t["id"] for t in self.consulta("SELECT id, numero FROM tickets")}
            for i in traidos["Encuestas"]:
                f = de_graph("Encuestas", i["fields"])
                tid = ids.get(f.pop("_numero") or "")
                if not tid or not f.get("enviada_en"):
                    continue
                self._ejecutar(
                    "INSERT INTO encuestas(id, ticket_id, ronda, token_hash, enviada_en, respondida_en, resultado, "
                    "csat, comentario) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "respondida_en = excluded.respondida_en, resultado = excluded.resultado, csat = excluded.csat, "
                    "comentario = excluded.comentario, token_hash = excluded.token_hash",
                    (i["id"], tid, int(f.get("ronda") or 1), f.get("token_hash") or f"sharepoint-{i['id']}",
                     iso(f["enviada_en"]), iso(f.get("respondida_en")), f.get("resultado") or C.PENDIENTE,
                     f.get("csat"), f.get("comentario")))
                self._anotar("Encuestas", i["id"], i["id"], i["etag"])
            for i in traidos["Eventos"]:
                f = de_graph("Eventos", i["fields"])
                tid = ids.get(f.pop("_numero") or "")
                if not tid or not f.get("en"):
                    continue
                self._ejecutar(
                    "INSERT INTO eventos(id, ticket_id, en, usuario, tipo, estado_desde, estado_hasta, publico, "
                    "detalle) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET detalle = excluded.detalle",
                    (i["id"], tid, iso(f["en"]), f.get("usuario") or "", f.get("tipo") or "estado",
                     f.get("estado_desde"), f.get("estado_hasta"), int(bool(f.get("publico"))), f.get("detalle") or ""))
            self._ejecutar("INSERT INTO sp_estado(clave, valor) VALUES ('ultima', ?) ON CONFLICT(clave) "
                           "DO UPDATE SET valor = excluded.valor", (inicio.isoformat(),))
        self.desactualizado = False
        return {lista: len(v) for lista, v in traidos.items()}

    def _traer_ticket(self, item: dict) -> None:
        f = de_graph("Tickets", item["fields"])
        if not f.get("numero") or not f.get("creado_en"):
            return                         # el flujo 1 lo está creando: llega en la próxima
        f["actualizado_en"] = f.get("actualizado_en") or f["creado_en"]
        f["reaperturas"] = f.get("reaperturas") or 0
        f["veces_en_espera"] = f.get("veces_en_espera") or 0
        f["conformidad"] = f.get("conformidad") or C.SIN_ENCUESTA
        f["estado"] = f.get("estado") or C.NUEVO
        f["asunto"] = f.get("asunto") or "(sin asunto)"
        f["solicitante_mail"] = (f.get("solicitante_mail") or "").lower()
        columnas = ["id", *f]
        valores = [item["id"], *(iso(v) if isinstance(v, datetime) else v for v in f.values())]
        cambios = ", ".join(f"{c} = excluded.{c}" for c in f)
        self._ejecutar(f"INSERT INTO tickets({', '.join(columnas)}) VALUES ({', '.join('?' for _ in columnas)}) "
                       f"ON CONFLICT(id) DO UPDATE SET {cambios}", valores)
        self._anotar("Tickets", item["id"], item["id"], item["etag"])


def enviador_tolerante(enviar, registro: list | None = None):
    """Un envío que, si falla, no deshace la operación: el `.eml` ya quedó en
    la carpeta de salida y el error se anota para mostrarlo. En modo
    compartido el ticket ya está en la lista cuando sale el correo; deshacer
    la operación local por un correo que no salió dejaría las dos copias
    distintas."""
    registro = registro if registro is not None else []

    def mandar(msg) -> None:
        try:
            enviar(msg)
        except Exception as error:   # noqa: BLE001 — se anota y se muestra, no se pierde
            registro.append(f"{msg['To']} · {msg['Subject']}: {error}")

    mandar.errores = registro
    return mandar
