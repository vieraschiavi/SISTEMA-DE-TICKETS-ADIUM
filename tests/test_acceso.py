"""El ingreso con la cuenta de Adium y lo que puede cada rol (con un doble de MSAL)."""
import pytest

from tickets_ec import acceso
from tickets_ec import catalogos as C
from tickets_ec.almacen import Almacen
from tickets_ec.config import Config, cargar

TENANT = "11111111-2222-3333-4444-555555555555"
CFG = Config(modo="compartida", entra_tenant=TENANT, entra_cliente="cliente", sharepoint_host="adium.sharepoint.com")


class MsalFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.cuentas = []
        self.pedido = {}

    def acquire_token_interactive(self, scopes, **kw):
        self.pedido = {"scopes": scopes, **kw}
        if "access_token" in self.respuesta:
            self.cuentas = [{"username": self.respuesta["id_token_claims"]["preferred_username"]}]
        return self.respuesta

    def get_accounts(self, username=None):
        return [c for c in self.cuentas if username in (None, c["username"])]

    def acquire_token_silent(self, scopes, account):
        return {"access_token": "renovado"} if account in self.cuentas else None

    def remove_account(self, cuenta):
        self.cuentas.remove(cuenta)


def _ok(mail="Ana.Perez@adium.com.uy", tid=TENANT):
    return {"access_token": "t", "id_token_claims": {"preferred_username": mail, "name": "Ana Pérez", "tid": tid}}


def test_ingresar_pide_los_permisos_delegados_y_devuelve_quien_es():
    app = MsalFalso(_ok())
    ses = acceso.Sesion(CFG, app=app)
    quien = ses.ingresar()
    assert (quien.mail, quien.nombre) == ("ana.perez@adium.com.uy", "Ana Pérez")
    assert set(app.pedido["scopes"]) == set(acceso.ALCANCES) and app.pedido["prompt"] == "select_account"
    assert ses.token() == "renovado"
    ses.salir()
    assert ses.quien is None and not app.cuentas
    with pytest.raises(acceso.ErrorAcceso, match="venció"):
        ses.token()


@pytest.mark.parametrize("respuesta, motivo", [
    (_ok(tid="otro-tenant"), "otra organización"),
    (_ok(mail="ana@gmail.com"), "no es una cuenta de Adium"),
    ({"error": "access_denied", "error_description": "El usuario canceló"}, "El usuario canceló")])
def test_cuentas_que_no_entran(respuesta, motivo):
    with pytest.raises(acceso.ErrorAcceso, match=motivo):
        acceso.Sesion(CFG, app=MsalFalso(respuesta)).ingresar()


def test_sin_configurar_dice_que_falta():
    with pytest.raises(acceso.ErrorAcceso, match="entra_tenant, entra_cliente, sharepoint_host"):
        acceso.Sesion(Config(modo="compartida"), app=MsalFalso(_ok()))


def test_roles_y_permisos():
    db = Almacen(":memory:")
    db.guardar_persona("ana@adium.com.uy", "Ana", C.EXCELENCIA, rol="analista")
    db.guardar_persona("coord@adium.com.uy", "Coord", C.EXCELENCIA, rol="coordinador")
    db.guardar_persona("baja@adium.com.uy", "Baja", C.DIGITAL, rol="analista", activo=False)
    db.guardar_persona("juan@adium.com.ar", "Juan")
    assert [acceso.rol(db, m) for m in ("ana@adium.com.uy", "coord@adium.com.uy", "baja@adium.com.uy",
                                        "juan@adium.com.ar", "nadie@adium.com.uy")] == [
        "analista", "coordinador", "", "", ""]
    libre = {"estado": C.NUEVO, "analista_mail": None}
    de_eli = {"estado": C.EN_CURSO, "analista_mail": "eli@adium.com.uy"}
    cerrado = {"estado": C.CERRADO, "analista_mail": "ana@adium.com.uy"}
    assert acceso.puede_actuar("analista", "ana@adium.com.uy", libre)
    assert not acceso.puede_actuar("analista", "ana@adium.com.uy", de_eli)
    assert not acceso.puede_actuar("analista", "ana@adium.com.uy", cerrado)
    assert acceso.puede_actuar("coordinador", "coord@adium.com.uy", de_eli)
    assert not acceso.puede_actuar("", "juan@adium.com.ar", libre)
    assert acceso.puede_asignar("coordinador") and not acceso.puede_asignar("analista")
    assert acceso.puede_configurar("coordinador") and not acceso.puede_configurar("analista")


def test_config_del_equipo_y_de_la_pc(tmp_path):
    equipo = tmp_path / "config.equipo.toml"
    equipo.write_text('modo = "compartida"\nentra_tenant = "t"\nsegundos_sync = 30\n', encoding="utf-8")
    propia = tmp_path / "config.toml"
    propia.write_text("segundos_sync = 120\n", encoding="utf-8")
    cfg = cargar(propia, entorno={}, equipo=equipo)
    assert (cfg.modo, cfg.entra_tenant, cfg.segundos_sync, cfg.compartida) == ("compartida", "t", 120, True)
    assert cfg.faltantes_compartida() == ["entra_cliente", "sharepoint_host"]
    assert cargar(tmp_path / "no", entorno={}, equipo=tmp_path / "no").compartida is False


def test_el_toml_del_equipo_tampoco_acepta_secretos_ni_modos_inventados(tmp_path):
    equipo = tmp_path / "config.equipo.toml"
    equipo.write_text('graph_secreto = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="secretos"):
        cargar(tmp_path / "no", entorno={}, equipo=equipo)
    equipo.write_text('modo = "nube"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="local o compartida"):
        cargar(tmp_path / "no", entorno={}, equipo=equipo)


def test_el_ejemplo_del_equipo_se_lee_y_no_trae_secretos():
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    cfg = cargar(raiz / "no-existe.toml", entorno={}, equipo=raiz / "config.equipo.ejemplo.toml")
    assert cfg.compartida and not cfg.envio_activo     # el envío sigue apagado por defecto


def test_si_microsoft_no_responde_se_dice_por_que(monkeypatch):
    import sys
    import types

    class Roto:
        def __init__(self, *a, **k):
            raise ValueError("Unable to get authority configuration")

    monkeypatch.setitem(sys.modules, "msal", types.SimpleNamespace(PublicClientApplication=Roto))
    with pytest.raises(acceso.ErrorAcceso, match="No se pudo contactar a Microsoft"):
        acceso.Sesion(CFG)

    class SinNavegador(MsalFalso):
        def acquire_token_interactive(self, scopes, **kw):
            raise RuntimeError("no hay navegador")

    with pytest.raises(acceso.ErrorAcceso, match="no hay navegador"):
        acceso.Sesion(CFG, app=SinNavegador({})).ingresar()
