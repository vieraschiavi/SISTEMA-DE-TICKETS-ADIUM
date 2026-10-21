"""
El correo de la casilla: leerlo, entender si es un pedido nuevo o la
respuesta a uno abierto, y escribir lo que la mesa contesta.

Tres fuentes, una sola forma de leer
------------------------------------
* `FuenteCarpeta` — una carpeta con archivos `.eml`. Es el camino que no
  necesita nada de IT más allá de la casilla: un flujo de Power Automate
  («Cuando llega un correo nuevo a un buzón compartido» → «Exportar correo»
  → «Crear archivo» en una carpeta de OneDrive/SharePoint sincronizada)
  deja cada correo como `.eml` y la mesa los procesa. Ver `docs/CASILLA.md`.
* `FuenteGraph` — Microsoft Graph con una app registrada en Entra ID
  (permiso de aplicación `Mail.ReadWrite`, acotado al buzón con una
  Application Access Policy). Es el camino recomendado en Microsoft 365.
* `FuenteIMAP` — cualquier servidor IMAP. En Exchange Online la
  autenticación básica está apagada: hace falta un token OAuth (XOAUTH2).

Las tres devuelven bytes MIME y `leer()` los convierte en un `Mensaje`.

Dos reglas que evitan los dos accidentes clásicos de una casilla de tickets
-----------------------------------------------------------------------
1. **Bucles.** Un «fuera de la oficina» que contesta el acuse de recibo, y
   el acuse que contesta al «fuera de la oficina», abren tickets hasta que
   alguien los corta. Todo correo automático (cabeceras `Auto-Submitted`,
   `X-Auto-Response-Suppress`, `Precedence: bulk`, asuntos de respuesta
   automática) y todo lo que manda la propia casilla se IGNORA, con el
   motivo anotado.
2. **Duplicados.** La misma fuente puede entregar un correo dos veces (un
   reintento de Power Automate, un IMAP que no llegó a marcar «leído»). El
   `Message-ID` se registra y un correo ya visto no vuelve a entrar.
"""
from __future__ import annotations

import hashlib
import html
import imaplib
import json
import re
import smtplib
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, make_msgid, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

#: Tope por adjunto que se guarda (los demás se anotan, no se guardan).
MAX_ADJUNTO = 15 * 1024 * 1024


@dataclass
class Adjunto:
    nombre: str
    tipo: str
    datos: bytes = field(repr=False)


@dataclass
class Mensaje:
    message_id: str
    remitente: str            # mail en minúscula
    nombre: str               # el nombre que trae el «De:»
    asunto: str
    cuerpo: str               # texto plano, sin el hilo citado
    fecha: datetime
    para: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    in_reply_to: str = ""
    referencias: list[str] = field(default_factory=list)
    adjuntos: list[Adjunto] = field(default_factory=list)
    automatico: str = ""       # motivo por el que es una respuesta automática, o vacío


# ==========================================================================
# Leer
# ==========================================================================
class _Texto(HTMLParser):
    """HTML → texto: el cuerpo de Outlook llega casi siempre sólo en HTML."""

    _BLOQUES = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._omitir = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head"):
            self._omitir += 1
        elif tag in self._BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head"):
            self._omitir = max(0, self._omitir - 1)
        elif tag in self._BLOQUES:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._omitir:
            self.partes.append(data)


def html_a_texto(contenido: str) -> str:
    p = _Texto()
    p.feed(contenido)
    texto = "".join(p.partes).replace("\xa0", " ")
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", texto).strip()


#: Dónde empieza el hilo citado, en los clientes de correo que usa Adium
#: (Outlook en español, inglés y portugués; Gmail; móviles).
_CITA = re.compile(
    r"^(\s*-{2,}\s*(mensaje original|original message|mensagem original)\s*-{2,}"
    r"|\s*(de|from|enviado|sent|von)\s*:\s.+"
    r"|\s*el .{4,80} escribi[oó]:\s*$|\s*on .{4,80} wrote:\s*$|\s*em .{4,80} escreveu:\s*$"
    r"|\s*_{10,}\s*$)",
    re.IGNORECASE | re.MULTILINE)


def sin_hilo(texto: str) -> str:
    """Lo que escribió la persona, sin el correo anterior que viene citado abajo."""
    m = _CITA.search(texto)
    cuerpo = texto[:m.start()] if m and m.start() > 0 else texto
    lineas = [ln for ln in cuerpo.splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lineas).strip()


_AUTO_ASUNTO = re.compile(
    r"^(respuesta autom[aá]tica|automatic reply|auto(matic)?[ -]?reply|resposta autom[aá]tica|"
    r"fuera de la oficina|out of (the )?office|aus(ente|encia)|undeliverable|no entregable|"
    r"delivery status notification|mail delivery (failed|subsystem))", re.IGNORECASE)


def _automatico(msg: EmailMessage, asunto: str) -> str:
    auto = (msg.get("Auto-Submitted") or "").strip().lower()
    if auto and auto != "no":
        return f"Auto-Submitted: {auto}"
    if msg.get("X-Auto-Response-Suppress") and "oof" in str(msg.get("X-Auto-Response-Suppress")).lower():
        return "X-Auto-Response-Suppress"
    if (msg.get("Precedence") or "").strip().lower() in ("bulk", "junk", "list", "auto_reply"):
        return f"Precedence: {msg.get('Precedence')}"
    if msg.get("X-Autoreply") or msg.get("X-Autorespond"):
        return "X-Autoreply"
    if _AUTO_ASUNTO.search(asunto.strip()):
        return "asunto de respuesta automática"
    return ""


def _nombre_seguro(nombre: str) -> str:
    """El nombre de un adjunto, sin rutas: `../../x.exe` → `x.exe`."""
    base = re.split(r"[\\/]", nombre or "adjunto")[-1]
    base = re.sub(r"[^\w.\- ()áéíóúñÁÉÍÓÚÑ]", "_", base).strip(" .") or "adjunto"
    return base[:120]


def leer(crudo: bytes) -> Mensaje:
    """Bytes MIME (un `.eml`) → `Mensaje`."""
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(crudo)
    asunto = re.sub(r"\s+", " ", str(msg.get("Subject") or "")).strip()
    de = getaddresses([str(msg.get("From") or "")])
    nombre, remitente = de[0] if de else ("", "")
    try:
        fecha_msg = parsedate_to_datetime(str(msg.get("Date"))) if msg.get("Date") else datetime.now()
    except (TypeError, ValueError):
        fecha_msg = datetime.now()
    if fecha_msg.tzinfo is not None:      # la mesa trabaja en hora local, sin zona
        fecha_msg = fecha_msg.astimezone().replace(tzinfo=None)
    message_id = str(msg.get("Message-ID") or "").strip()
    if not message_id:                    # sin Message-ID, uno estable a partir del contenido
        message_id = f"<sin-id-{hashlib.sha256(crudo).hexdigest()[:24]}@tickets>"

    cuerpo = msg.get_body(preferencelist=("plain", "html"))
    texto = ""
    if cuerpo is not None:
        contenido = cuerpo.get_content()
        texto = html_a_texto(contenido) if cuerpo.get_content_type() == "text/html" else contenido
    adjuntos = []
    for parte in msg.iter_attachments():
        datos = parte.get_payload(decode=True) or b""
        adjuntos.append(Adjunto(_nombre_seguro(parte.get_filename() or "adjunto"),
                                parte.get_content_type(), datos))
    referencias = str(msg.get("References") or "").split()
    return Mensaje(
        message_id=message_id, remitente=(remitente or "").strip().lower(),
        nombre=(nombre or remitente.split("@")[0]).strip(), asunto=asunto or "(sin asunto)",
        cuerpo=sin_hilo(texto.strip()), fecha=fecha_msg,
        para=[m.lower() for _n, m in getaddresses([str(msg.get("To") or "")]) if m],
        cc=[m.lower() for _n, m in getaddresses([str(msg.get("Cc") or "")]) if m],
        in_reply_to=str(msg.get("In-Reply-To") or "").strip(), referencias=referencias,
        adjuntos=adjuntos, automatico=_automatico(msg, asunto))


def numero_en_asunto(asunto: str, prefijo: str) -> str | None:
    """`RE: [EC-00042] Tablero de OLE` → `EC-00042`."""
    m = re.search(rf"\[\s*({re.escape(prefijo)}-\d{{5,}})\s*\]", asunto, re.IGNORECASE)
    return m.group(1).upper() if m else None


def asunto_limpio(asunto: str) -> str:
    """Sin `RE:`, `RV:`, `FW:` ni el número del ticket."""
    s = re.sub(r"^\s*((re|rv|fw|fwd|enc|res)\s*:\s*)+", "", asunto, flags=re.IGNORECASE)
    s = re.sub(r"\[\s*[A-Z]+-\d{5,}\s*\]\s*", "", s)
    return s.strip() or "(sin asunto)"


# ==========================================================================
# Escribir
# ==========================================================================
def armar(de: str, nombre_de: str, para: str, asunto: str, texto: str, html_cuerpo: str,
          en_respuesta_a: str = "", cc: list[str] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"{nombre_de} <{de}>"
    msg["To"] = para
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = asunto
    msg["Message-ID"] = make_msgid(domain=de.split("@")[-1])
    # Que el «fuera de la oficina» del otro lado no conteste esto.
    msg["Auto-Submitted"] = "auto-generated"
    msg["X-Auto-Response-Suppress"] = "All"
    if en_respuesta_a:
        msg["In-Reply-To"] = en_respuesta_a
        msg["References"] = en_respuesta_a
    msg.set_content(texto)
    msg.add_alternative(html_cuerpo, subtype="html")
    return msg


class BuzonSalida:
    """Lo que la mesa manda. SIEMPRE se escribe el `.eml` en la carpeta de
    salida (es el registro de qué se le dijo a quién); sólo con
    `envio_activo` además se envía."""

    def __init__(self, carpeta: Path | None, enviar=None):
        self.carpeta = Path(carpeta) if carpeta else None
        self.enviar = enviar           # callable(EmailMessage) o None
        self.enviados: list[EmailMessage] = []

    def mandar(self, msg: EmailMessage) -> str:
        self.enviados.append(msg)
        destino = ""
        if self.carpeta:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            sello = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            etiqueta = re.sub(r"[^\w-]", "_", str(msg["Subject"]))[:60]
            ruta = self.carpeta / f"{sello}_{etiqueta}.eml"
            ruta.write_bytes(bytes(msg))
            destino = str(ruta)
        if self.enviar:
            self.enviar(msg)
        return destino


# ==========================================================================
# Fuentes
# ==========================================================================
class FuenteCarpeta:
    """Los `.eml` de una carpeta. Los procesados se mueven a `procesados/`."""

    def __init__(self, carpeta: Path):
        self.carpeta = Path(carpeta)

    def leer(self):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        for ruta in sorted(self.carpeta.glob("*.eml")):
            yield ruta.name, ruta.read_bytes()

    def confirmar(self, clave: str) -> None:
        hecho = self.carpeta / "procesados"
        hecho.mkdir(exist_ok=True)
        origen = self.carpeta / clave
        if origen.exists():
            origen.replace(hecho / clave)


def _pedir(url: str, *, metodo: str = "GET", datos: bytes | None = None, token: str = "",
           tipo: str = "application/json", abrir=urllib.request.urlopen) -> bytes:
    req = urllib.request.Request(url, data=datos, method=metodo)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if datos is not None:
        req.add_header("Content-Type", tipo)
    with abrir(req, timeout=30) as r:
        return r.read()


class FuenteGraph:
    """El buzón compartido por Microsoft Graph (credenciales de aplicación).

    Lee los no leídos de la bandeja de entrada, baja cada uno en MIME y lo
    marca leído recién cuando la mesa confirma que lo registró: si el
    proceso se corta en el medio, el correo se vuelve a leer y el
    `Message-ID` evita el duplicado.
    """

    BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, tenant: str, cliente: str, secreto: str, buzon: str, abrir=urllib.request.urlopen,
                 token=None):
        if not buzon or not (token or (tenant and cliente and secreto)):
            raise ValueError("Graph necesita tenant, cliente, secreto (TICKETS_GRAPH_SECRETO) y buzón.")
        self.tenant, self.cliente, self.secreto, self.buzon = tenant, cliente, secreto, buzon
        self.abrir = abrir
        self._token = ""
        self._delegado = token

    @classmethod
    def delegada(cls, buzon: str, token, abrir=urllib.request.urlopen) -> FuenteGraph:
        """El buzón con la cuenta de la persona que usa la app (modo compartido):
        `token` es `acceso.Sesion.token`. Necesita Acceso total al buzón
        compartido (y «Enviar como» para mandar), que da IT."""
        return cls("", "", "", buzon, abrir, token=token)

    def token(self) -> str:
        if self._delegado:
            return self._delegado()
        if not self._token:
            cuerpo = urllib.parse.urlencode({
                "client_id": self.cliente, "client_secret": self.secreto, "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default"}).encode()
            r = _pedir(f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token", metodo="POST",
                       datos=cuerpo, tipo="application/x-www-form-urlencoded", abrir=self.abrir)
            self._token = json.loads(r)["access_token"]
        return self._token

    def _url_buzon(self) -> str:
        return f"{self.BASE}/users/{urllib.parse.quote(self.buzon)}"

    def leer(self):
        filtro = urllib.parse.quote("isRead eq false")
        url = f"{self._url_buzon()}/mailFolders/inbox/messages?$filter={filtro}&$select=id&$top=50"
        lista = json.loads(_pedir(url, token=self.token(), abrir=self.abrir))
        for m in lista.get("value", []):
            yield m["id"], _pedir(f"{self._url_buzon()}/messages/{m['id']}/$value", token=self.token(),
                                  abrir=self.abrir)

    def confirmar(self, clave: str) -> None:
        _pedir(f"{self._url_buzon()}/messages/{clave}", metodo="PATCH", datos=b'{"isRead": true}',
               token=self.token(), abrir=self.abrir)

    def enviar(self, msg: EmailMessage) -> None:
        """Manda en MIME (base64) desde el buzón: queda en sus «Enviados»."""
        import base64
        _pedir(f"{self._url_buzon()}/sendMail", metodo="POST", datos=base64.b64encode(bytes(msg)),
               token=self.token(), tipo="text/plain", abrir=self.abrir)


class FuenteIMAP:
    """Un buzón IMAP. Con `token` usa XOAUTH2 (lo que pide Exchange Online)."""

    def __init__(self, host: str, usuario: str, clave: str = "", token: str = "", carpeta: str = "INBOX",
                 conectar=imaplib.IMAP4_SSL):
        self.host, self.usuario, self.clave, self.token, self.carpeta = host, usuario, clave, token, carpeta
        self._conectar = conectar
        self._imap = None

    def _sesion(self):
        if self._imap is None:
            imap = self._conectar(self.host)
            if self.token:
                cadena = f"user={self.usuario}\x01auth=Bearer {self.token}\x01\x01"
                imap.authenticate("XOAUTH2", lambda _x: cadena.encode())
            else:
                imap.login(self.usuario, self.clave)
            imap.select(self.carpeta)
            self._imap = imap
        return self._imap

    def leer(self):
        imap = self._sesion()
        _r, datos = imap.search(None, "UNSEEN")
        for uid in (datos[0] or b"").split():
            _r, partes = imap.fetch(uid, "(BODY.PEEK[])")
            yield uid.decode(), partes[0][1]

    def confirmar(self, clave: str) -> None:
        self._sesion().store(clave, "+FLAGS", "\\Seen")


def enviador_smtp(host: str, puerto: int, usuario: str, clave: str):
    def enviar(msg: EmailMessage) -> None:
        with smtplib.SMTP(host, puerto, timeout=30) as s:
            s.starttls()
            s.login(usuario, clave)
            s.send_message(msg)
    return enviar


def escapar(texto: str) -> str:
    return html.escape(texto or "", quote=True)
