"""
La app en modo local, corrida de verdad con `streamlit.testing` (AppTest) sobre una demo corta en disco: los
botones que llevan de una página a otra y los filtros de la bandeja. Dos de estos casos rompían en la PC de un
usuario y ningún test los recorría (el E2E sólo abre cada página).
"""
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from tickets_ec import catalogos as C  # noqa: E402
from tickets_ec import config as config_mod  # noqa: E402
from tickets_ec import demo  # noqa: E402
from tickets_ec.config import Config  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "app.py")


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    ruta = tmp_path_factory.mktemp("demo") / "tickets.db"
    demo.generar(ruta, hasta=datetime(2025, 7, 1, 12, 0))
    return ruta


@pytest.fixture
def app(base, tmp_path, monkeypatch):
    import streamlit as st

    st.cache_resource.clear()
    cfg = Config(base=base, carpeta_salida=tmp_path / "salida", carpeta_adjuntos=tmp_path / "adjuntos",
                 directorio=Path("/no-existe.csv"))
    monkeypatch.setattr(config_mod, "cargar", lambda *a, **k: cfg)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    yield at
    st.cache_resource.clear()


def _cerrado() -> str:
    """Un ticket cerrado: con el filtro de estado por defecto (los abiertos) no se ve."""
    from tickets_ec.almacen import Almacen
    return Almacen(config_mod.cargar().base).tickets("estado = ?", (C.CERRADO,))[0]["numero"]


def test_abrir_desde_inicio_lleva_al_ticket(app):
    boton = next(b for b in app.button if b.label == "Abrir")
    boton.click().run()
    assert not app.exception, app.exception
    assert app.sidebar.radio[0].value == "🎫 Ticket"
    assert any(m.value.startswith("## #EC-") for m in app.markdown)


def test_la_bandeja_con_estado_vacio_y_una_busqueda_no_rompe(app):
    numero = _cerrado()
    app.sidebar.radio[0].set_value("📥 Bandeja").run()
    estado = next(m for m in app.multiselect if m.label == "Estado")
    estado.set_value([]).run()                         # vacío = todos los estados
    app.text_input[0].input(numero).run()
    assert not app.exception, app.exception
    assert any("1 tickets" in c.value for c in app.caption)
    tabla = app.dataframe[0].value
    assert list(tabla["Número"]) == [numero]


def test_una_busqueda_sin_resultados_muestra_cero(app):
    app.sidebar.radio[0].set_value("📥 Bandeja").run()
    app.text_input[0].input("no-existe-nada-asi").run()
    assert not app.exception, app.exception
    assert any("0 tickets" in c.value for c in app.caption)
