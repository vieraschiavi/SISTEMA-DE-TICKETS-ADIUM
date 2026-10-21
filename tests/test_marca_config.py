import tomllib
from pathlib import Path

import pytest

from tickets_ec import config, marca

RAIZ = Path(__file__).resolve().parent.parent


def test_contraste():
    for frente, fondo, donde in marca.PARES_DE_TEXTO:
        assert marca.contraste(frente, fondo) >= 4.5, donde


def test_tema_de_streamlit_igual_a_la_marca():
    tema = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text())["theme"]
    assert tema == marca.TEMA


def test_colores_iguales_a_los_de_la_suite():
    suite = RAIZ.parent / "Power-bi" / "AdiumAllinOne" / "adium_allinone" / "marca.py"
    if not suite.is_file():
        pytest.skip("la suite no está al lado")
    texto = suite.read_text()
    for nombre in ("AZUL", "ROJO", "GRIS", "BORDE", "VERDE", "ROJO_ALERTA", "FONDO", "ROJO_TEXTO", "VERDE_TEXTO",
                   "AMBAR"):
        assert f'{nombre} = "{getattr(marca, nombre)}"' in texto, nombre


def test_secretos_en_el_toml_se_rechazan(tmp_path):
    (tmp_path / "c.toml").write_text('graph_secreto = "x"\n')
    with pytest.raises(ValueError, match="secretos"):
        config.cargar(tmp_path / "c.toml", entorno={})


def test_entorno_pisa_al_toml(tmp_path):
    (tmp_path / "c.toml").write_text('casilla = "a@b.c"\ndias_conformidad_tacita = 5\n')
    c = config.cargar(tmp_path / "c.toml", entorno={"TICKETS_CASILLA": "z@b.c", "TICKETS_ENVIO_ACTIVO": "1"})
    assert (c.casilla, c.dias_conformidad_tacita, c.envio_activo) == ("z@b.c", 5, True)


def test_el_envio_sale_apagado():
    assert config.Config().envio_activo is False
