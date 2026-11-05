"""
La app en modo compartido, corrida de verdad con `streamlit.testing`
(AppTest), con un doble de Microsoft (el ingreso) y de SharePoint (las
listas). Ve lo que un test del motor no ve: que sin cuenta no se pasa, que
una cuenta que no es del equipo no entra y que un analista no puede trabajar
el ticket de otro.
"""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402
from test_compartida import ListasFalsas  # noqa: E402

from tickets_ec import acceso, compartida  # noqa: E402
from tickets_ec import catalogos as C  # noqa: E402
from tickets_ec import config as config_mod  # noqa: E402
from tickets_ec import correo as CO  # noqa: E402
from tickets_ec.config import Config  # noqa: E402
from tickets_ec.servicio import Mesa  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "app.py")
ANA, ELI = "ana@adium.com.uy", "eli@adium.com.uy"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    import streamlit as st

    st.cache_resource.clear()
    listas = ListasFalsas()
    cfg = Config(modo="compartida", entra_tenant="t", entra_cliente="c", sharepoint_host="adium.sharepoint.com",
                 base=tmp_path / "datos" / "tickets.db", carpeta_salida=tmp_path / "salida",
                 carpeta_adjuntos=tmp_path / "adjuntos", directorio=Path("/no-existe.csv"),
                 casilla_automatica=True, segundos_sync=0)       # que cada pantalla sincronice
    quien = {"mail": ANA}

    class SesionFalsa:
        def __init__(self, _cfg):
            self.quien = None

        def ingresar(self):
            self.quien = acceso.Identidad(quien["mail"], quien["mail"].split("@")[0].capitalize())
            return self.quien

        def token(self):
            return "tok"

        def salir(self):
            self.quien = None

    monkeypatch.setattr(config_mod, "cargar", lambda *a, **k: cfg)
    monkeypatch.setattr(acceso, "Sesion", SesionFalsa)
    monkeypatch.setattr(compartida, "ListasGraph", lambda *a, **k: listas)
    # El equipo y un ticket de Eli, cargados desde «otra PC».
    otra = Mesa(compartida.AlmacenCompartido(":memory:", listas), cfg)
    otra.alta_analista(ANA, "Ana", equipo=C.EXCELENCIA)
    otra.alta_analista(ELI, "Eli", equipo=C.EXCELENCIA)
    t = otra.crear("Share de pantoprazol", "IQVIA", "juan@adium.com.ar", "Juan")
    otra.asignar(t["numero"], ELI, ELI)
    # La casilla compartida: se anota quién la lee, sin salir a la red.
    leidas: list[str] = []
    monkeypatch.setattr(CO.FuenteGraph, "leer", lambda self: leidas.append(quien["mail"]) or iter(()))
    yield {"listas": listas, "quien": quien, "numero": t["numero"], "leidas": leidas}
    st.cache_resource.clear()


def _entrar(at: AppTest) -> AppTest:
    at.run(timeout=60)
    boton = next(b for b in at.button if "Ingresar con mi cuenta" in b.label)
    boton.click()
    return at.run(timeout=60)


def test_sin_cuenta_no_se_pasa_y_con_cuenta_se_ve_la_mesa_de_todos(entorno):
    at = AppTest.from_file(APP)
    at.run(timeout=60)
    assert not at.exception
    assert any("Ingresar con mi cuenta de Adium" in b.label for b in at.button)
    assert not at.sidebar.radio                         # nada de la mesa antes de entrar
    _entrar(at)
    assert not at.exception
    assert any("Ana" in m.value and "analista" in m.value for m in at.sidebar.markdown)
    assert not at.sidebar.selectbox                     # ya no se elige «Actuás como»
    # El ticket que cargó «la otra PC» cuenta en la mesa de Ana.
    assert any("<div class='n'>1</div><div class='t'>Pendientes del equipo" in m.value for m in at.markdown)


def test_una_cuenta_que_no_es_del_equipo_ve_solo_el_portal_y_pide_desde_ahi(entorno):
    entorno["quien"]["mail"] = "paula@adium.com.uy"
    at = _entrar(AppTest.from_file(APP))
    assert not at.exception
    assert list(at.sidebar.radio[0].options) == ["🌐 Portal"]       # ni bandeja, ni indicadores, ni configuración
    assert any("Paula" in m.value and "solicitante" in m.value for m in at.sidebar.markdown)
    at.radio(key="portal_vista").set_value("➕ Enviar un ticket").run(timeout=60)
    assert not at.exception
    at.selectbox(key="pt_tipo").set_value("Solicitud de permisos").run(timeout=60)
    assert any("con qué rol" in i.value for i in at.info)              # la ayuda del tipo elegido
    at.text_input(key="pt_asunto").input("Acceso al tablero de Close Up")
    at.text_area(key="pt_desc").input("Para mí, lectura")
    next(b for b in at.button if b.label == "Enviar").click()
    at.run(timeout=60)
    assert not at.exception
    assert any("Recibimos tu pedido" in m.value for m in at.success)
    (nuevo,) = [i["fields"] for i in entorno["listas"].datos["Tickets"].values()
                if i["fields"].get("SolicitanteMail") == "paula@adium.com.uy"]
    assert (nuevo["Canal"], nuevo["Tipo"]) == ("Portal", "Solicitud de permisos")
    # Lo ve en «Mis tickets», y no ve el de Juan que cargó la otra PC.
    assert any(nuevo["Numero"] in m.value for m in at.markdown)
    assert not any(entorno["numero"] in m.value for m in at.markdown)
    assert entorno["leidas"] == []       # su PC no lee la casilla compartida (no tiene acceso)


def test_el_equipo_tambien_tiene_el_portal_y_su_pc_lee_la_casilla(entorno):
    at = _entrar(AppTest.from_file(APP))
    assert "🌐 Portal" in at.sidebar.radio[0].options and "📥 Bandeja" in at.sidebar.radio[0].options
    assert entorno["leidas"] and set(entorno["leidas"]) == {ANA}


def test_el_analista_no_trabaja_el_ticket_de_otro(entorno):
    at = _entrar(AppTest.from_file(APP))
    at.session_state["pagina"] = "🎫 Ticket"
    at.session_state["ticket"] = entorno["numero"]
    at.run(timeout=60)
    assert not at.exception
    assert any("Lo tiene Eli" in i.value for i in at.info)
    assert not any("Tomarlo" in b.label for b in at.button)
    actualizar = next(b for b in at.button if b.label == "Actualizar")
    assert actualizar.disabled
