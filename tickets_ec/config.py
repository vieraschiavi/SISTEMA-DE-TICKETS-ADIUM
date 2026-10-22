"""
La configuración de la mesa: casilla, URL de la app, calendario laboral y
conectores de correo.

Se lee de cuatro lados, en este orden y ganando el último: los valores por
defecto de acá, `config.equipo.toml` (lo mismo para todo el equipo: el modo
compartido, el tenant, el sitio; viaja en el paquete de la suite), un
`config.toml` (el de esta PC, ver `config.ejemplo.toml`) y variables de
entorno `TICKETS_*`. Los secretos (clave de Graph, contraseña IMAP, la sal de
las encuestas) van SÓLO por entorno: un `.toml` termina commiteado.

Lo que este módulo NO hace: prender un conector. El envío de correos sale
apagado (`envio_activo = False`): con él apagado, cada correo se escribe como
`.eml` en la carpeta de salida y nada sale de la máquina.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Feriados de Uruguay (HQ) de 2025 y 2026, los de día fijo y los móviles
#: (Carnaval y Semana de Turismo). Se reemplazan por `feriados` en el toml.
FERIADOS_UY = tuple(date.fromisoformat(d) for d in (
    "2025-01-01", "2025-01-06", "2025-03-03", "2025-03-04", "2025-04-14", "2025-04-15", "2025-04-16",
    "2025-04-17", "2025-04-18", "2025-05-01", "2025-05-19", "2025-06-19", "2025-07-18", "2025-08-25",
    "2025-10-13", "2025-11-02", "2025-12-25",
    "2026-01-01", "2026-01-06", "2026-02-16", "2026-02-17", "2026-03-30", "2026-03-31", "2026-04-01",
    "2026-04-02", "2026-04-03", "2026-05-01", "2026-05-18", "2026-06-19", "2026-07-18", "2026-08-25",
    "2026-10-12", "2026-11-02", "2026-12-25",
))


@dataclass(frozen=True)
class Config:
    # --- La casilla ---------------------------------------------------------
    casilla: str = "tickets.excelenciacomercial@adium.com.uy"
    nombre_casilla: str = "Tickets · Excelencia Comercial & Digital"
    prefijo: str = "EC"
    #: Dominios propios: un correo de otro dominio entra igual, pero con área
    #: «Sin área» hasta que alguien la complete.
    dominios: tuple[str, ...] = ("adium.com.uy", "adium.com.ar", "adium.com.br", "adium.cl", "adium.com.co",
                                 "adium.com.mx", "adium.com.pe", "adium.com.py", "adium.com.ec",
                                 "adium.com.bo", "adium.com.ve", "adium.net")
    #: Dominio → país, para el solicitante que no está en el directorio.
    pais_por_dominio: dict = field(default_factory=lambda: {
        "adium.com.uy": "Uruguay (HQ)", "adium.com.ar": "Argentina", "adium.com.br": "Brasil",
        "adium.cl": "Chile", "adium.com.co": "Colombia", "adium.com.mx": "México", "adium.com.pe": "Perú",
        "adium.com.py": "Paraguay", "adium.com.ec": "Ecuador", "adium.com.bo": "Bolivia",
        "adium.com.ve": "Venezuela"})

    # --- La app ------------------------------------------------------------
    url_app: str = "http://localhost:8750"
    base: Path = RAIZ / "datos" / "tickets.db"
    carpeta_salida: Path = RAIZ / "datos" / "salida"
    carpeta_adjuntos: Path = RAIZ / "datos" / "adjuntos"
    carpeta_entrada: Path = RAIZ / "datos" / "entrada"
    directorio: Path = RAIZ / "datos" / "directorio.csv"

    # --- Modo de trabajo ------------------------------------------------------
    #: "local": la base es un SQLite en esta PC (una persona, o la demo).
    #: "compartida": cada integrante abre la app (o la suite) en SU PC, entra
    #: con su cuenta de Microsoft de Adium y todos leen y escriben las mismas
    #: listas de SharePoint; la casilla las alimenta. Ver docs/EQUIPO.md.
    modo: str = "local"
    #: La app de Entra ID de la mesa: cliente PÚBLICO (sin secreto), con
    #: `http://localhost` como URI de redirección. Ninguno de los dos es un
    #: secreto: identifican la app, no la autorizan.
    entra_tenant: str = ""
    entra_cliente: str = ""
    #: Cada cuánto se trae lo que cambiaron los demás (y se lee la casilla).
    segundos_sync: int = 60
    #: En modo compartido, cada sincronización lee también la casilla y cierra
    #: lo tácito. Dos PCs que leen el mismo correo no lo duplican: la primera
    #: que lo reclama en la lista Correos se lo queda.
    casilla_automatica: bool = True

    # --- Calendario laboral --------------------------------------------------
    hora_inicio: int = 9
    hora_fin: int = 18
    feriados: tuple[date, ...] = FERIADOS_UY
    #: Días hábiles sin respuesta a la encuesta tras los que se cierra solo.
    dias_conformidad_tacita: int = 3

    # --- Conectores (apagados por defecto) ---------------------------------
    #: "carpeta" (los .eml que deja Power Automate), "graph" o "imap".
    fuente: str = "carpeta"
    envio_activo: bool = False
    #: "graph" o "smtp".
    envio: str = "graph"
    graph_tenant: str = ""
    graph_cliente: str = ""
    imap_host: str = "outlook.office365.com"
    imap_usuario: str = ""
    #: El sitio de SharePoint de la mesa (camino Power Platform).
    sharepoint_host: str = ""                 # p. ej. «adium.sharepoint.com»
    sharepoint_sitio: str = "/sites/TicketsEC"
    smtp_host: str = "smtp.office365.com"
    smtp_puerto: int = 587

    # --- Secretos: sólo por entorno ---------------------------------------
    @property
    def graph_secreto(self) -> str:
        return os.environ.get("TICKETS_GRAPH_SECRETO", "")

    @property
    def imap_clave(self) -> str:
        return os.environ.get("TICKETS_IMAP_CLAVE", "")

    @property
    def smtp_clave(self) -> str:
        return os.environ.get("TICKETS_SMTP_CLAVE", "")

    @property
    def secreto(self) -> str:
        """La sal de las encuestas. Sin ella las encuestas funcionan igual
        (el token es aleatorio y se guarda su hash), pero el link no se
        puede firmar contra manipulación del número de ticket."""
        return os.environ.get("TICKETS_SECRETO", "")

    @property
    def compartida(self) -> bool:
        return self.modo == "compartida"

    def faltantes_compartida(self) -> list[str]:
        """Lo que el modo compartido necesita y no está configurado."""
        if not self.compartida:
            return []
        return [k for k in ("entra_tenant", "entra_cliente", "sharepoint_host", "sharepoint_sitio")
                if not getattr(self, k)]


_SECRETOS = {"graph_secreto", "imap_clave", "smtp_clave", "secreto"}


def _convertir(campo, valor):
    tipo = str(campo.type)
    if "Path" in tipo:
        return Path(valor)
    if tipo == "bool":
        return valor if isinstance(valor, bool) else str(valor).strip().lower() in ("1", "true", "si", "sí", "yes")
    if tipo == "int":
        return int(valor)
    if "tuple[date" in tipo:
        return tuple(v if isinstance(v, date) else date.fromisoformat(str(v)) for v in valor)
    if "tuple" in tipo:
        return tuple(str(v).strip() for v in (valor.split(",") if isinstance(valor, str) else valor))
    return valor


MODOS = ("local", "compartida")


def cargar(ruta: Path | str | None = None, entorno: dict | None = None,
           equipo: Path | str | None = None) -> Config:
    """Defaults → `config.equipo.toml` → `config.toml` → `TICKETS_<CAMPO>`.
    Un secreto en un toml se rechaza con nombre: si está ahí, ya está en un
    lugar que se comparte."""
    entorno = os.environ if entorno is None else entorno
    cfg = Config()
    ruta = Path(ruta) if ruta else Path(entorno.get("TICKETS_CONFIG", RAIZ / "config.toml"))
    equipo = Path(equipo) if equipo else Path(entorno.get("TICKETS_CONFIG_EQUIPO", RAIZ / "config.equipo.toml"))
    cambios: dict = {}
    campos = {f.name: f for f in fields(Config)}
    for archivo in (equipo, ruta):
        if not archivo.is_file():
            continue
        datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
        secretos = _SECRETOS & set(datos)
        if secretos:
            raise ValueError(f"{archivo.name} trae secretos ({', '.join(sorted(secretos))}): "
                             "van por variable de entorno TICKETS_*, nunca en un archivo.")
        for k, v in datos.items():
            if k in campos:
                cambios[k] = _convertir(campos[k], v)
    for k, f in campos.items():
        v = entorno.get(f"TICKETS_{k.upper()}")
        if v not in (None, ""):
            cambios[k] = _convertir(f, v)
    cfg = replace(cfg, **cambios)
    if cfg.modo not in MODOS:
        raise ValueError(f"modo = «{cfg.modo}»: tiene que ser {' o '.join(MODOS)}.")
    return cfg
