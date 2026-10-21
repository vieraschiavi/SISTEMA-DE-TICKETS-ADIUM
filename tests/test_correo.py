from tickets_ec import correo as CO

EML = b"""From: =?utf-8?q?Juli=C3=A1n_P=C3=A9rez?= <Julian.Perez@adium.com.ar>
To: tickets.excelenciacomercial@adium.com.uy
Cc: jefa@adium.com.ar
Subject: RE: [EC-00042] Tablero de OLE
Message-ID: <abc@mail>
In-Reply-To: <orig@mail>
Date: Mon, 19 Oct 2026 10:00:00 -0300
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="X"

--X
Content-Type: text/html; charset=utf-8

<html><head><style>p{color:red}</style></head><body><p>Hola, va el dato.</p>
<p>Saludos</p><div>De: Tickets &lt;tickets@adium.com.uy&gt;<br>Enviado: lunes</div><p>texto viejo</p></body></html>
--X
Content-Type: application/pdf
Content-Disposition: attachment; filename="../../etc/passwd.pdf"

JVBERi0=
--X--
"""


def test_lee_html_sin_hilo_y_adjunto_seguro():
    m = CO.leer(EML)
    assert m.remitente == "julian.perez@adium.com.ar"
    assert m.nombre == "Julián Pérez"
    assert "va el dato" in m.cuerpo and "texto viejo" not in m.cuerpo and "color" not in m.cuerpo
    assert m.cc == ["jefa@adium.com.ar"]
    assert m.in_reply_to == "<orig@mail>"
    assert m.adjuntos[0].nombre == "passwd.pdf"
    assert not m.automatico


def test_numero_y_asunto_limpio():
    assert CO.numero_en_asunto("RE: [EC-00042] Tablero", "EC") == "EC-00042"
    assert CO.numero_en_asunto("Tablero EC-00042", "EC") is None
    assert CO.asunto_limpio("RE: RV: [EC-00042] Tablero de OLE") == "Tablero de OLE"


def test_detecta_respuestas_automaticas():
    oof = EML.replace(b"Subject: RE: [EC-00042] Tablero de OLE", b"Subject: Respuesta autom\xc3\xa1tica: fuera")
    assert CO.leer(oof).automatico
    auto = EML.replace(b"MIME-Version", b"Auto-Submitted: auto-replied\nMIME-Version")
    assert "Auto-Submitted" in CO.leer(auto).automatico


def test_sin_message_id_genera_uno_estable():
    sin = EML.replace(b"Message-ID: <abc@mail>\n", b"")
    assert CO.leer(sin).message_id == CO.leer(sin).message_id.strip()
    assert CO.leer(sin).message_id.startswith("<sin-id-")


def test_lo_que_manda_la_mesa_pide_no_ser_contestado():
    msg = CO.armar("t@adium.com.uy", "Tickets", "a@b.c", "[EC-00001] x", "hola", "<p>hola</p>")
    assert msg["Auto-Submitted"] == "auto-generated"


def test_fuente_carpeta_mueve_lo_procesado(tmp_path):
    (tmp_path / "a.eml").write_bytes(EML)
    f = CO.FuenteCarpeta(tmp_path)
    claves = [c for c, _ in f.leer()]
    f.confirmar(claves[0])
    assert not (tmp_path / "a.eml").exists() and (tmp_path / "procesados" / "a.eml").exists()


class _Resp:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_fuente_graph_lee_y_marca_leido():
    pedidos = []

    def abrir(req, timeout=30):
        pedidos.append((req.get_method(), req.full_url))
        if "oauth2" in req.full_url:
            return _Resp(b'{"access_token": "tok"}')
        if req.full_url.endswith("/$value"):
            return _Resp(EML)
        if "messages?" in req.full_url:
            return _Resp(b'{"value": [{"id": "m1"}]}')
        return _Resp(b"{}")

    g = CO.FuenteGraph("ten", "cli", "sec", "tickets@adium.com.uy", abrir=abrir)
    leidos = list(g.leer())
    assert leidos[0][0] == "m1" and leidos[0][1] == EML
    g.confirmar("m1")
    assert ("PATCH", "https://graph.microsoft.com/v1.0/users/tickets%40adium.com.uy/messages/m1") in pedidos
