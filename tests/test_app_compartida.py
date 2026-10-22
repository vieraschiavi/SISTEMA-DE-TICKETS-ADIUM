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
                 casilla_automatica=False)
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
    yield {"listas": listas, "quien": quien, "numero": t["numero"]}
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


def test_una_cuenta_que_no_es_del_equipo_no_entra(entorno):
    entorno["quien"]["mail"] = "juan@adium.com.ar"
    at = _entrar(AppTest.from_file(APP))
    assert not at.exception
    assert any("no está en la lista **Personas**" in e.value for e in at.error)


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
