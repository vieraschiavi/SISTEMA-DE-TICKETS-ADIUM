"""
El modo compartido con dos PCs de verdad (dos `Mesa`, dos copias locales)
sobre las mismas listas. Las listas son un doble en memoria con lo que
importa de SharePoint: ids que da la lista, eTag por versión (412 si no
coincide), `Modified`, y valores únicos en el Title de Correos (409).
"""
import io
import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tickets_ec import catalogos as C
from tickets_ec import compartida as CP
from tickets_ec import correo as CO
from tickets_ec.config import Config
from tickets_ec.servicio import Mesa, voto_por_correo
from tickets_ec.sharepoint import UNICAS

ANA, ELI, COORD = "ana@adium.com.uy", "eli@adium.com.uy", "coord@adium.com.uy"
JUAN = "juan@adium.com.ar"


class ListasFalsas:
    def __init__(self):
        self.datos: dict[str, dict[int, dict]] = {}
        self.ids: dict[str, int] = {}
        self.sin_red: set[str] = set()
        self.pedidos: list[tuple] = []

    def _lista(self, lista):
        return self.datos.setdefault(lista, {})

    @staticmethod
    def _etag(lista, item_id, version):
        return f'"{lista}-{item_id},{version}"'

    def _red(self, lista):
        if lista in self.sin_red:
            raise CP.ErrorListas("Sin conexión con SharePoint (prueba)")

    def crear(self, lista, campos):
        self._red(lista)
        self.pedidos.append(("POST", lista))
        for col in UNICAS.get(lista, ()):
            if any(i["fields"].get(col) == campos.get(col) for i in self._lista(lista).values()):
                raise CP.Duplicado(f"{col} duplicado")
        item_id = self.ids[lista] = self.ids.get(lista, 0) + 1
        self._lista(lista)[item_id] = {"fields": dict(campos), "version": 1, "mod": datetime.now(UTC)}
        return item_id, self._etag(lista, item_id, 1)

    def actualizar(self, lista, item_id, campos, etag=None):
        self._red(lista)
        self.pedidos.append(("PATCH", lista))
        i = self._lista(lista)[item_id]
        if etag not in (None, "*") and etag != self._etag(lista, item_id, i["version"]):
            raise CP.Conflicto("Otro integrante cambió este ticket")
        i["fields"].update(campos)
        i["version"] += 1
        i["mod"] = datetime.now(UTC)
        return self._etag(lista, item_id, i["version"])

    def borrar(self, lista, item_id):
        self._lista(lista).pop(item_id)

    def _salida(self, lista, item_id, i):
        return {"id": item_id, "etag": self._etag(lista, item_id, i["version"]), "fields": dict(i["fields"])}

    def items(self, lista, desde=None):
        self._red(lista)
        return [self._salida(lista, k, i) for k, i in self._lista(lista).items() if not desde or i["mod"] >= desde]

    def buscar(self, lista, campo, valor):
        return [self._salida(lista, k, i) for k, i in self._lista(lista).items() if i["fields"].get(campo) == valor]


class Reloj:
    def __init__(self):
        self.ahora = datetime(2026, 10, 19, 10, 0)

    def __call__(self):
        return self.ahora


@pytest.fixture
def listas():
    return ListasFalsas()


def _cfg(tmp_path, quien):
    return Config(modo="compartida", entra_tenant="t", entra_cliente="c", sharepoint_host="adium.sharepoint.com",
                  directorio=Path("/no-existe.csv"), carpeta_salida=tmp_path / quien / "salida",
                  carpeta_adjuntos=tmp_path / quien / "adjuntos")


@pytest.fixture
def dos_pcs(tmp_path, listas):
    """La PC de Ana y la de Eli, con el equipo cargado desde la de Ana."""
    reloj = Reloj()
    a = Mesa(CP.AlmacenCompartido(":memory:", listas), _cfg(tmp_path, "ana"), reloj=reloj)
    b = Mesa(CP.AlmacenCompartido(":memory:", listas), _cfg(tmp_path, "eli"), reloj=reloj)
    a.alta_analista(ANA, "Ana", equipo=C.EXCELENCIA)
    a.alta_analista(ELI, "Eli", equipo=C.EXCELENCIA)
    a.alta_analista(COORD, "Coord", coordinador=True)
    b.db.sincronizar()
    return a, b


def _mail(asunto="Necesito el share de pantoprazol", mid="<a1@x>", de=JUAN, cuerpo="IQVIA TAM"):
    return CO.Mensaje(mid, de, "Juan Gómez", asunto, cuerpo, None)


def test_lo_que_entra_en_una_pc_lo_ve_la_otra_con_el_mismo_numero(dos_pcs, listas):
    a, b = dos_pcs
    assert {p["mail"] for p in b.db.analistas()} == {ANA, ELI, COORD}
    r = a.procesar_correo(_mail())
    assert r.numero == "EC-00001"                   # el número sale del id de la lista
    b.db.sincronizar()
    t = b.db.ticket("EC-00001")
    assert (t["estado"], t["solicitante_mail"], t["tipo"]) == (C.NUEVO, JUAN, "Pedido de información")
    assert [e["tipo"] for e in b.db.eventos(t["id"])] == [e["tipo"] for e in a.db.eventos(t["id"])]
    assert all(e["id"] > 0 for e in a.db.eventos())      # los ids provisorios se reemplazaron al subir


def test_si_los_dos_lo_toman_a_la_vez_el_segundo_choca_y_nada_se_pisa(dos_pcs, listas):
    a, b = dos_pcs
    numero = a.procesar_correo(_mail()).numero
    b.db.sincronizar()
    a.tomar(numero, ANA)
    with pytest.raises(CP.Conflicto, match="Otro integrante"):
        b.tomar(numero, ELI)                         # Eli tenía la versión de antes
    assert b.db.desactualizado
    assert b.db.ticket(numero)["analista_mail"] is None    # su copia no quedó a medias
    b.db.sincronizar()
    t = b.db.ticket(numero)
    assert (t["estado"], t["analista_mail"]) == (C.EN_CURSO, ANA)
    estados = [i["fields"]["EstadoHasta"] for i in listas.datos["Eventos"].values() if i["fields"]["Title"] == "estado"]
    assert estados == [C.NUEVO, C.ASIGNADO, C.EN_CURSO]  # ningún evento del intento de Eli


def test_el_mismo_correo_leido_por_dos_pcs_abre_un_solo_ticket(dos_pcs, listas):
    a, b = dos_pcs
    assert a.procesar_correo(_mail()).resultado == "nuevo"
    assert b.procesar_correo(_mail()).resultado == "ignorado: ya procesado"
    assert len(listas.datos["Tickets"]) == 1
    (correo,) = listas.datos["Correos"].values()
    assert (correo["fields"]["Title"], correo["fields"]["Resultado"], correo["fields"]["TicketNumero"]) == (
        "<a1@x>", "nuevo", "EC-00001")


def test_si_procesar_falla_el_correo_queda_libre_para_otra_pc(dos_pcs, listas, monkeypatch):
    a, b = dos_pcs

    def roto(_m):
        raise RuntimeError("se cortó")

    monkeypatch.setattr(a, "_procesar", roto)
    with pytest.raises(RuntimeError):
        a.procesar_correo(_mail())
    assert not listas.datos.get("Correos")          # soltó el candado
    assert b.procesar_correo(_mail()).resultado == "nuevo"


def test_sin_red_los_eventos_esperan_en_la_cola_y_suben_despues(dos_pcs, listas):
    a, b = dos_pcs
    numero = a.procesar_correo(_mail()).numero
    listas.sin_red.add("Eventos")
    a.comentar(numero, "Lo miro mañana", ANA)
    assert a.db.pendientes == 1 and "Sin conexión" in a.db.error_subida
    t = a.db.ticket(numero)
    assert a.db.eventos(t["id"], "comentario")[0]["id"] < 0     # se ve en la PC aunque no subió
    listas.sin_red.clear()
    a.db.sincronizar()
    assert a.db.pendientes == 0 and a.db.error_subida == ""
    b.db.sincronizar()
    assert [e["detalle"] for e in b.db.eventos(t["id"], "comentario")] == ["Lo miro mañana"]
    assert len(a.db.eventos(t["id"], "comentario")) == 1        # subió una vez, sin duplicarse


def test_la_encuesta_se_contesta_por_correo_desde_cualquier_pc(dos_pcs, listas):
    a, b = dos_pcs
    numero = a.procesar_correo(_mail()).numero
    a.tomar(numero, ANA)
    a.resolver(numero, "Te mandé el Excel", ANA)
    resuelto = a.salida.enviados[-1]
    html = resuelto.get_body(("html",)).get_content()
    assert f"mailto:{a.cfg.casilla}?subject=%5B{numero}%5D%20Conforme" in html   # no hay app que abrir
    b.db.sincronizar()
    r = b.procesar_correo(_mail(f"[{numero}] Conforme", "<a2@x>", cuerpo="5\nGracias, impecable"))
    assert r.resultado == "encuesta"
    a.db.sincronizar()
    t = a.db.ticket(numero)
    assert (t["estado"], t["conformidad"], t["csat"]) == (C.CERRADO, C.CONFORME, 5)
    (enc,) = listas.datos["Encuestas"].values()
    assert (enc["fields"]["Resultado"], enc["fields"]["Comentario"]) == (C.CONFORME, "Gracias, impecable")


def test_no_conforme_por_correo_reabre_con_el_texto_como_comentario(dos_pcs):
    a, _b = dos_pcs
    numero = a.procesar_correo(_mail()).numero
    a.tomar(numero, ANA)
    a.resolver(numero, "Listo", ANA)
    a.procesar_correo(_mail(f"RE: [{numero}] No conforme", "<a3@x>", cuerpo="Falta Uruguay"))
    t = a.db.ticket(numero)
    assert (t["estado"], t["conformidad"], t["reaperturas"]) == (C.REABIERTO, C.NO_CONFORME, 1)


@pytest.mark.parametrize("asunto, voto", [
    ("[EC-00042] Conforme", True), ("RE: [EC-00042] Sí, conforme", True), ("RV: [EC-00042] No conforme", False),
    ("RE: [EC-00042] Resuelto: el share", None), ("Conformes con el tablero nuevo", None)])
def test_voto_por_correo(asunto, voto):
    assert voto_por_correo(asunto) is voto


def test_las_fechas_viajan_en_utc_y_vuelven_en_hora_local():
    local = datetime(2026, 10, 21, 9, 30)
    campos = CP.a_graph("Tickets", {"creado_en": local, "asunto": "x" * 300, "reaperturas": 0})
    assert campos["CreadoEn"].endswith("Z") and len(campos["Title"]) == CP.MAX_TEXTO
    assert CP.de_graph("Tickets", campos)["creado_en"] == local


# ==========================================================================
# El cliente HTTP contra Graph
# ==========================================================================
class _Resp:
    def __init__(self, cuerpo):
        self.cuerpo = json.dumps(cuerpo).encode()

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _cliente(respuestas):
    vistos = []

    def abrir(req, timeout=30):
        vistos.append(req)
        r = respuestas.pop(0)
        if isinstance(r, int):
            raise urllib.error.HTTPError(req.full_url, r, "x", {}, io.BytesIO(b'{"error": "x"}'))
        return _Resp(r)

    c = CP.ListasGraph("adium.sharepoint.com", "/sites/TicketsEC", lambda: "tok", abrir=abrir)
    return c, vistos


def test_actualizar_manda_if_match_y_un_412_es_conflicto():
    c, vistos = _cliente([{"id": "sitio-1"}, {"@odata.etag": '"g,3"'}, 412])
    assert c.actualizar("Tickets", 7, {"Estado": "En curso"}, '"g,2"') == '"g,3"'
    req = vistos[1]
    assert req.get_method() == "PATCH" and req.full_url.endswith("/sites/sitio-1/lists/Tickets/items/7/fields")
    assert req.get_header("If-match") == '"g,2"' and req.get_header("Authorization") == "Bearer tok"
    with pytest.raises(CP.Conflicto):
        c.actualizar("Tickets", 7, {"Estado": "Resuelto"}, '"g,2"')


def test_crear_un_correo_repetido_es_duplicado_y_un_403_dice_que_falta_permiso():
    c, _ = _cliente([{"id": "s"}, 409, 403])
    with pytest.raises(CP.Duplicado):
        c.crear("Correos", {"Title": "<a@x>"})
    with pytest.raises(CP.ErrorListas, match="edición en el sitio"):
        c.crear("Tickets", {"Title": "x"})


def test_items_filtra_por_modified_y_sigue_las_paginas():
    c, vistos = _cliente([{"id": "s"},
                          {"value": [{"id": "1", "eTag": '"a,1"', "fields": {"Title": "uno"}}],
                           "@odata.nextLink": "https://graph.microsoft.com/v1.0/siguiente"},
                          {"value": [{"id": "2", "eTag": '"b,1"', "fields": {"Title": "dos"}}]}])
    filas = c.items("Tickets", datetime(2026, 10, 21, 12, 0, tzinfo=UTC))
    assert [(f["id"], f["fields"]["Title"]) for f in filas] == [(1, "uno"), (2, "dos")]
    assert "$filter=fields/Modified%20ge%20%272026-10-21T12%3A00%3A00Z%27" in vistos[1].full_url
    assert vistos[2].full_url.endswith("/siguiente")


def test_un_envio_que_falla_no_deshace_la_operacion():
    def roto(_msg):
        raise OSError("sin red")

    enviar = CP.enviador_tolerante(roto)
    msg = CO.armar("casilla@adium.com.uy", "Mesa", JUAN, "[EC-00001] Hola", "hola", "<p>hola</p>")
    enviar(msg)
    assert enviar.errores and "sin red" in enviar.errores[0]


def test_el_cierre_tacito_en_dos_pcs_cierra_una_vez_y_no_frena_a_la_segunda(dos_pcs, listas):
    a, b = dos_pcs
    numero = a.procesar_correo(_mail()).numero
    a.tomar(numero, ANA)
    a.resolver(numero, "Listo", ANA)
    b.db.sincronizar()
    a.reloj.ahora = datetime(2026, 10, 26, 10, 0)    # cinco días hábiles después
    assert a.cierre_tacito() == [numero]
    assert b.cierre_tacito() == []                   # su copia era vieja: choca, saltea y sigue
    b.db.sincronizar()
    assert b.db.ticket(numero)["conformidad"] == C.TACITA
    cierres = [i for i in listas.datos["Eventos"].values() if i["fields"].get("EstadoHasta") == C.CERRADO]
    assert len(cierres) == 1
