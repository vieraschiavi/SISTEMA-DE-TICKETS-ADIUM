import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import generar_powerplatform as G  # noqa: E402

from tickets_ec import sharepoint  # noqa: E402


def test_lo_commiteado_esta_al_dia_con_los_catalogos():
    for nombre, contenido in G.archivos().items():
        ruta = (G.DESTINO / nombre).resolve()
        assert ruta.read_text(encoding="utf-8") == contenido, (
            f"{nombre} quedó viejo: corré python scripts/generar_powerplatform.py")


def test_el_script_crea_todas_las_listas_y_columnas():
    ps = G.powershell()
    for lista, cols in sharepoint.LISTAS.items():
        assert f"Asegurar-Lista '{lista}'" in ps
        for interno, *_ in cols:
            if interno != "Title":
                assert f"'{lista}' '{interno}'" in ps


def test_nombres_internos_sin_espacios_ni_acentos():
    for cols in sharepoint.LISTAS.values():
        for interno, *_ in cols:
            assert interno.isascii() and interno.isalnum(), interno
