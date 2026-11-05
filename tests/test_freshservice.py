"""El conector con FreshService de IT, contra un doble de su API v2 (filtro, solicitantes, estado y notas)."""
import base64
import io
import json
import urllib.error
import urllib.parse
from dataclasses import replace
from pathlib import Path

import pytest

from tickets_ec import catalogos as C
from tickets_ec import compartida as CP
from tickets_ec import correo as CO
from tickets_ec import freshservice as FS
from tickets_ec.config import Config
from tickets_ec.servicio import Mesa

ANA = "ana@adium.com.uy"
DOMINIO = "mesa-demo.freshservice.test"


class _Resp:
    def __init__(self, cuerpo):
        self.cuerpo = json.dumps(cuerpo).encode()

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FreshServiceFalso:
    def __init__(self):
        self.tickets = {101: {"id": 101, "subject": "Share de pantoprazol por país", "status": 2,
                              "description_text": "IQVIA MAT, todos los países", "requester_id": 7,
                              "cc_emails": ["Paula@adium.com.uy"], "created_at": "2026-10-19T13:00:00Z",
                              "custom_fields": {"incidencia_en": "Reportería Excelencia Comercial"}},
                        102: {"id": 102, "subject": "Acceso al tablero de Close Up", "status": 2,
                              "description_text": "Lectura", "requester_id": 9, "cc_emails": [],
                              "created_at": "2026-10-19T14:00:00Z",
                              "custom_fields": {"incidencia_en": "Reportería Excelencia Comercial"}}}
        self.requesters = {7: {"primary_email": "Juan@adium.com.ar", "first_name": "Juan", "last_name": "Gómez"}}
        self.agents = {9: {"email": "it.lucia@adium.com.uy", "first_name": "Lucía", "last_name": ""}}
        self.pedidos: list[tuple] = []
        self.notas: dict[int, list[dict]] = {}

    def __call__(self, req, timeout=30):
        url = urllib.parse.urlparse(req.full_url)
        ruta = url.path.removeprefix("/api/v2")
        cuerpo = json.loads(req.data) if req.data else None
        self.pedidos.append((req.get_method(), ruta, urllib.parse.unquote(url.query), cuerpo,
                             req.get_header("Authorization")))
        partes = ruta.strip("/").split("/")
        if req.get_method() == "GET" and ruta == "/tickets/filter":
            abiertos = [t for t in self.tickets.values() if t["status"] in (2, 3)]
            return _Resp({"tickets": abiertos, "total": len(abiertos)})
        if partes[0] in ("requesters", "agents"):
            fuente = self.requesters if partes[0] == "requesters" else self.agents
            if int(partes[1]) not in fuente:
                raise urllib.error.HTTPError(req.full_url, 404, "x", {}, io.BytesIO(b"{}"))
            return _Resp({partes[0][:-1]: fuente[int(partes[1])]})
        if req.get_method() == "PUT" and partes[0] == "tickets":
            self.tickets[int(partes[1])].update(cuerpo)
            return _Resp({"ticket": self.tickets[int(partes[1])]})
        if req.get_method() == "POST" and partes[-1] == "notes":
            self.notas.setdefault(int(partes[1]), []).append(cuerpo)
            return _Resp({"conversation": cuerpo})
        raise AssertionError(f"ruta inesperada {req.get_method()} {ruta}")


@pytest.fixture
def fs():
    return FreshServiceFalso()


@pytest.fixture
def cfg_fs(cfg):
    return replace(cfg, freshservice_activo=True, freshservice_dominio=DOMINIO, freshservice_campo="incidencia_en")


@pytest.fixture
def con_clave(monkeypatch):
    monkeypatch.setenv("TICKETS_FRESHSERVICE_CLAVE", "clave-de-prueba")


def test_importa_una_vez_con_el_solicitante_de_freshservice(mesa, cfg_fs, fs, con_clave):
    mesa.cfg = cfg_fs
    res = FS.sincronizar(mesa, cfg_fs, abrir=fs)
    nuevos = [r for r in res if r.resultado == "nuevo"]
    assert len(nuevos) == 2
    t = mesa.db.ticket(nuevos[0].numero)
    assert (t["canal"], t["solicitante_mail"], t["solicitante_nombre"], t["cc"]) == (
        "FreshService", "juan@adium.com.ar", "Juan Gómez", "paula@adium.com.uy")
    assert FS.id_de(t["message_id"]) == 101
    # El agente de IT que pidió algo también entra (su ficha es de agente, no de solicitante).
    assert mesa.db.ticket(nuevos[1].numero)["solicitante_mail"] == "it.lucia@adium.com.uy"
    nota = fs.notas[101][0]
    assert nota["private"] is False and nuevos[0].numero in nota["body"]
    # La consulta: el campo de la opción, sólo lo abierto o pendiente, entre comillas dobles.
    metodo, _ruta, query, _c, auth = fs.pedidos[0]
    assert query.startswith('query="(incidencia_en:\'Reportería Excelencia Comercial\') AND (status:2 OR status:3)"')
    assert auth == "Basic " + base64.b64encode(b"clave-de-prueba:X").decode()
    # La segunda vuelta no duplica nada ni vuelve a escribir en FreshService.
    antes = len(fs.pedidos)
    assert [r for r in FS.sincronizar(mesa, cfg_fs, abrir=fs) if r.resultado == "nuevo"] == []
    assert all(m == "GET" for m, *_ in fs.pedidos[antes:])
    assert len(mesa.db.tickets()) == 2


def test_el_estado_vuelve_a_freshservice_y_la_resolucion_como_nota(mesa, cfg_fs, fs, con_clave):
    FS.sincronizar(mesa, cfg_fs, abrir=fs)
    numero = mesa.db.tickets("canal = ?", ("FreshService",))[0]["numero"]
    mesa.tomar(numero, ANA)
    assert [r for r in FS.sincronizar(mesa, cfg_fs, abrir=fs) if r.numero == numero] == []   # sigue «Abierto»
    mesa.pedir_informacion(numero, "¿Qué países?", ANA)
    FS.sincronizar(mesa, cfg_fs, abrir=fs)
    assert fs.tickets[101]["status"] == FS.PENDIENTE
    mesa.procesar_correo(CO.Mensaje("<r1@x>", "juan@adium.com.ar", "Juan", f"RE: [{numero}] Share", "Todos", None))
    mesa.resolver(numero, "Te mandé el Excel con todos los países", ANA)
    FS.sincronizar(mesa, cfg_fs, abrir=fs)
    assert fs.tickets[101]["status"] == FS.RESUELTO
    assert "Te mandé el Excel" in fs.notas[101][-1]["body"]
    mesa.reloj.avanzar(days=6)
    mesa.cierre_tacito()
    notas = len(fs.notas[101])
    FS.sincronizar(mesa, cfg_fs, abrir=fs)
    assert fs.tickets[101]["status"] == FS.CERRADO and len(fs.notas[101]) == notas   # la resolución, una vez
    assert any("estado 5" in e["detalle"] for e in mesa.db.eventos(mesa.db.ticket(numero)["id"], FS.EVENTO))


def test_apagado_no_habla_con_nadie_y_sin_campo_dice_que_falta(mesa, cfg, fs, con_clave):
    assert FS.sincronizar(mesa, cfg, abrir=fs) == [] and fs.pedidos == []
    sin_campo = replace(cfg, freshservice_activo=True, freshservice_dominio=DOMINIO)
    with pytest.raises(FS.ErrorFreshService, match="freshservice_campo"):
        FS.sincronizar(mesa, sin_campo, abrir=fs)
    por_grupo = replace(sin_campo, freshservice_filtro="group_id:1234")
    assert FS.filtro(por_grupo) == "(group_id:1234) AND (status:2 OR status:3)"


def test_sin_clave_no_arranca(mesa, cfg_fs, fs, monkeypatch):
    monkeypatch.delenv("TICKETS_FRESHSERVICE_CLAVE", raising=False)
    with pytest.raises(FS.ErrorFreshService, match="TICKETS_FRESHSERVICE_CLAVE"):
        FS.sincronizar(mesa, cfg_fs, abrir=fs)


def test_dos_pcs_del_modo_compartido_no_lo_importan_dos_veces(tmp_path, fs, con_clave):
    from test_compartida import ListasFalsas

    listas = ListasFalsas()
    cfg = Config(modo="compartida", entra_tenant="t", entra_cliente="c", sharepoint_host="h",
                 directorio=Path("/no-existe.csv"), carpeta_salida=tmp_path / "s", carpeta_adjuntos=tmp_path / "a",
                 freshservice_activo=True, freshservice_dominio=DOMINIO, freshservice_campo="incidencia_en")
    a = Mesa(CP.AlmacenCompartido(":memory:", listas), cfg)
    b = Mesa(CP.AlmacenCompartido(":memory:", listas), cfg)
    FS.importar(a, FS.ClienteFreshService(DOMINIO, "k", fs), cfg)
    res_b = FS.importar(b, FS.ClienteFreshService(DOMINIO, "k", fs), cfg)       # B no sincronizó todavía
    assert {r.resultado for r in res_b} == {"ignorado: ya importado"}
    assert len(listas.datos["Tickets"]) == 2 and len(fs.notas[101]) == 1


def test_la_clave_de_freshservice_no_va_en_un_toml(tmp_path):
    from tickets_ec.config import cargar
    t = tmp_path / "config.toml"
    t.write_text('freshservice_clave = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="secretos"):
        cargar(t, entorno={}, equipo=tmp_path / "no")
    assert C.CANALES[-1] == "FreshService"
