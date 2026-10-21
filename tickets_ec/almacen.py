"""
Dónde viven los tickets: SQLite, con el mismo esquema que `sql/01_esquema.sql`
crea en SQL Server.

SQLite porque la mesa tiene que andar el primer día en la PC del equipo sin
pedirle nada a IT; el esquema es el mismo que el de SQL Server para que el
paso a una base corporativa sea cambiar el destino del export, no rehacer el
modelo. Las fechas se guardan como texto ISO (`2026-10-21T09:15:00`): ordenan
bien como texto y Power BI las lee como fecha y hora sin transformar.

Toda escritura pasa por `transaccion()`: un cambio de estado escribe el
ticket Y su evento, o ninguno de los dos. Un evento sin el ticket actualizado
(o al revés) es un tablero que no cierra contra la bandeja.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS personas (
    mail        TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    area        TEXT,
    pais        TEXT,
    rol         TEXT NOT NULL DEFAULT 'solicitante',   -- solicitante | analista | coordinador
    activo      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS tickets (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    numero                TEXT UNIQUE,
    asunto                TEXT NOT NULL,
    descripcion           TEXT,
    solicitante_mail      TEXT NOT NULL,
    solicitante_nombre    TEXT,
    area                  TEXT,
    pais                  TEXT,
    tipo                  TEXT,          -- tipo de ticket: Nuevo desarrollo, Pedido de información, Permisos…
    subtipo               TEXT,
    atc                   TEXT,          -- clase terapéutica (CT) del pedido, si es de un mercado
    area_terapeutica      TEXT,
    unidad_negocio        TEXT,
    mercado               TEXT,          -- mercado conformado de HQ, si se nombró
    fuente_datos          TEXT,
    tablero               TEXT,          -- el informe o tablero que se pide cambiar o abrir
    prioridad             TEXT,
    canal                 TEXT,
    estado                TEXT NOT NULL,
    subestado             TEXT,
    equipo                TEXT,          -- equipo resolutor: Excelencia Comercial | Digital
    analista_mail         TEXT,
    cc                    TEXT,
    clasificacion         TEXT,          -- por qué el clasificador eligió tipo y prioridad
    message_id            TEXT,
    creado_en             TEXT NOT NULL,
    actualizado_en        TEXT NOT NULL,
    asignado_en           TEXT,
    primera_respuesta_en  TEXT,
    en_curso_en           TEXT,
    resuelto_en           TEXT,
    cerrado_en            TEXT,
    cancelado_en          TEXT,
    reaperturas           INTEGER NOT NULL DEFAULT 0,
    veces_en_espera       INTEGER NOT NULL DEFAULT 0,
    conformidad           TEXT NOT NULL DEFAULT 'Sin encuesta',
    csat                  INTEGER,
    resolucion            TEXT
);
CREATE INDEX IF NOT EXISTS ix_tickets_estado ON tickets(estado);
CREATE INDEX IF NOT EXISTS ix_tickets_analista ON tickets(analista_mail);
CREATE TABLE IF NOT EXISTS eventos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     INTEGER NOT NULL REFERENCES tickets(id),
    en            TEXT NOT NULL,
    usuario       TEXT NOT NULL,
    tipo          TEXT NOT NULL,   -- estado | asignacion | prioridad | tipo | comentario | correo_entrante | correo_saliente | encuesta
    estado_desde  TEXT,
    estado_hasta  TEXT,
    publico       INTEGER NOT NULL DEFAULT 0,
    detalle       TEXT
);
CREATE INDEX IF NOT EXISTS ix_eventos_ticket ON eventos(ticket_id, en);
CREATE TABLE IF NOT EXISTS encuestas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     INTEGER NOT NULL REFERENCES tickets(id),
    ronda         INTEGER NOT NULL,
    token_hash    TEXT NOT NULL UNIQUE,
    enviada_en    TEXT NOT NULL,
    respondida_en TEXT,
    resultado     TEXT NOT NULL DEFAULT 'Pendiente',
    csat          INTEGER,
    comentario    TEXT
);
CREATE TABLE IF NOT EXISTS correos (
    message_id    TEXT PRIMARY KEY,
    ticket_id     INTEGER REFERENCES tickets(id),
    recibido_en   TEXT NOT NULL,
    remitente     TEXT,
    asunto        TEXT,
    resultado     TEXT NOT NULL      -- nuevo | respuesta | ignorado: <motivo>
);
"""

_FECHAS_TICKET = ("creado_en", "actualizado_en", "asignado_en", "primera_respuesta_en", "en_curso_en",
                  "resuelto_en", "cerrado_en", "cancelado_en")


def iso(momento: datetime | None) -> str | None:
    return momento.replace(microsecond=0).isoformat() if momento else None


def fecha(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


def _fila(cursor, fila) -> dict:
    d = {c[0]: v for c, v in zip(cursor.description, fila, strict=True)}
    for k in _FECHAS_TICKET + ("en", "enviada_en", "respondida_en", "recibido_en"):
        if k in d and isinstance(d[k], str):
            d[k] = fecha(d[k])
    return d


class Almacen:
    """Acceso a la base. `ruta=":memory:"` para tests y para la demo."""

    def __init__(self, ruta: str | Path):
        self.ruta = str(ruta)
        if self.ruta != ":memory:":
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.ruta, check_same_thread=False)
        self._con.row_factory = _fila
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.executescript(ESQUEMA)
        self._en_transaccion = False
        # Las columnas que se pueden escribir: los nombres de `insertar_ticket`
        # y `actualizar_ticket` van al SQL tal cual, así que se validan acá.
        self._columnas = {f["name"] for f in self.consulta("PRAGMA table_info(tickets)")}

    # ---- transacciones ----------------------------------------------------
    @contextmanager
    def transaccion(self):
        if self._en_transaccion:          # anidada: la de afuera confirma
            yield self
            return
        self._en_transaccion = True
        try:
            yield self
            self._con.commit()
        except Exception:
            self._con.rollback()
            raise
        finally:
            self._en_transaccion = False

    def _ejecutar(self, sql: str, params=()) -> sqlite3.Cursor:
        cur = self._con.execute(sql, params)
        if not self._en_transaccion:
            self._con.commit()
        return cur

    def consulta(self, sql: str, params=()) -> list[dict]:
        return self._con.execute(sql, params).fetchall()

    # ---- personas ---------------------------------------------------------
    def guardar_persona(self, mail: str, nombre: str, area: str | None = None, pais: str | None = None,
                        rol: str = "solicitante", activo: bool = True) -> None:
        self._ejecutar(
            "INSERT INTO personas(mail, nombre, area, pais, rol, activo) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(mail) DO UPDATE SET nombre=excluded.nombre, area=COALESCE(excluded.area, area), "
            "pais=COALESCE(excluded.pais, pais), rol=excluded.rol, activo=excluded.activo",
            (mail.lower(), nombre, area, pais, rol, int(activo)))

    def persona(self, mail: str) -> dict | None:
        filas = self.consulta("SELECT * FROM personas WHERE mail = ?", (mail.lower(),))
        return filas[0] if filas else None

    def analistas(self, solo_activos: bool = True) -> list[dict]:
        sql = "SELECT * FROM personas WHERE rol IN ('analista', 'coordinador')"
        return self.consulta(sql + (" AND activo = 1" if solo_activos else "") + " ORDER BY nombre")

    # ---- tickets ----------------------------------------------------------
    def _validar_columnas(self, campos: dict) -> None:
        ajenas = set(campos) - self._columnas
        if ajenas:
            raise ValueError(f"Columnas que la tabla tickets no tiene: {', '.join(sorted(ajenas))}")

    def insertar_ticket(self, prefijo: str, **campos) -> dict:
        self._validar_columnas(campos)
        columnas = ", ".join(campos)
        marcas = ", ".join("?" for _ in campos)
        valores = [iso(v) if isinstance(v, datetime) else v for v in campos.values()]
        cur = self._ejecutar(f"INSERT INTO tickets({columnas}) VALUES ({marcas})", valores)
        numero = f"{prefijo}-{cur.lastrowid:05d}"
        self._ejecutar("UPDATE tickets SET numero = ? WHERE id = ?", (numero, cur.lastrowid))
        return self.ticket(numero)

    def actualizar_ticket(self, ticket_id: int, **campos) -> None:
        if not campos:
            return
        self._validar_columnas(campos)
        asignaciones = ", ".join(f"{k} = ?" for k in campos)
        valores = [iso(v) if isinstance(v, datetime) else v for v in campos.values()]
        self._ejecutar(f"UPDATE tickets SET {asignaciones} WHERE id = ?", (*valores, ticket_id))

    def ticket(self, numero: str) -> dict | None:
        filas = self.consulta("SELECT * FROM tickets WHERE numero = ?", (numero.upper(),))
        return filas[0] if filas else None

    def ticket_por_message_id(self, message_id: str) -> dict | None:
        filas = self.consulta(
            "SELECT t.* FROM tickets t LEFT JOIN correos c ON c.ticket_id = t.id "
            "WHERE t.message_id = ? OR c.message_id = ? LIMIT 1", (message_id, message_id))
        return filas[0] if filas else None

    def tickets(self, donde: str = "", params=()) -> list[dict]:
        return self.consulta(f"SELECT * FROM tickets {('WHERE ' + donde) if donde else ''} ORDER BY id", params)

    # ---- eventos ----------------------------------------------------------
    def agregar_evento(self, ticket_id: int, en: datetime, usuario: str, tipo: str, *,
                       estado_desde: str | None = None, estado_hasta: str | None = None,
                       publico: bool = False, detalle: str = "") -> None:
        self._ejecutar(
            "INSERT INTO eventos(ticket_id, en, usuario, tipo, estado_desde, estado_hasta, publico, detalle) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ticket_id, iso(en), usuario, tipo, estado_desde, estado_hasta, int(publico), detalle))

    def eventos(self, ticket_id: int | None = None, tipo: str | None = None) -> list[dict]:
        donde, params = [], []
        if ticket_id is not None:
            donde.append("ticket_id = ?")
            params.append(ticket_id)
        if tipo:
            donde.append("tipo = ?")
            params.append(tipo)
        sql = "SELECT * FROM eventos" + (" WHERE " + " AND ".join(donde) if donde else "")
        return self.consulta(sql + " ORDER BY en, id", params)

    # ---- encuestas --------------------------------------------------------
    def agregar_encuesta(self, ticket_id: int, ronda: int, token_hash: str, enviada_en: datetime) -> None:
        self._ejecutar("INSERT INTO encuestas(ticket_id, ronda, token_hash, enviada_en) VALUES (?,?,?,?)",
                       (ticket_id, ronda, token_hash, iso(enviada_en)))

    def encuesta_por_hash(self, token_hash: str) -> dict | None:
        filas = self.consulta("SELECT * FROM encuestas WHERE token_hash = ?", (token_hash,))
        return filas[0] if filas else None

    def responder_encuesta(self, encuesta_id: int, en: datetime, resultado: str, csat: int | None,
                           comentario: str) -> None:
        self._ejecutar("UPDATE encuestas SET respondida_en = ?, resultado = ?, csat = ?, comentario = ? "
                       "WHERE id = ?", (iso(en), resultado, csat, comentario, encuesta_id))

    def encuestas(self) -> list[dict]:
        return self.consulta("SELECT * FROM encuestas ORDER BY id")

    def encuestas_pendientes(self) -> list[dict]:
        return self.consulta("SELECT * FROM encuestas WHERE resultado = 'Pendiente' ORDER BY enviada_en")

    # ---- correos (idempotencia de la ingesta) --------------------------
    def correo_visto(self, message_id: str) -> bool:
        return bool(self.consulta("SELECT 1 FROM correos WHERE message_id = ?", (message_id,)))

    def registrar_correo(self, message_id: str, ticket_id: int | None, recibido_en: datetime,
                         remitente: str, asunto: str, resultado: str) -> None:
        self._ejecutar("INSERT OR IGNORE INTO correos(message_id, ticket_id, recibido_en, remitente, asunto, "
                       "resultado) VALUES (?,?,?,?,?,?)",
                       (message_id, ticket_id, iso(recibido_en), remitente, asunto, resultado))

    def correos(self) -> list[dict]:
        return self.consulta("SELECT * FROM correos ORDER BY recibido_en DESC")

    def cerrar(self) -> None:
        self._con.close()
