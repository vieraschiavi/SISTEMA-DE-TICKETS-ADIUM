"""El tablero entero: se arma con la suite y cada KPI se verifica contra Python.
Lento (~30 s) y necesita la suite al lado; sin ella se salta."""
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SUITE = Path(os.environ.get("ADIUM_SUITE", RAIZ.parent / "Power-bi"))


@pytest.mark.skipif(not (SUITE / "AdiumAllinOne").is_dir(), reason="la suite Adium All in One no está al lado")
def test_el_tablero_sale_listo_y_con_los_numeros_de_la_app(tmp_path):
    pytest.importorskip("pandas")
    sys.path.insert(0, str(RAIZ / "powerbi"))
    import armar_tablero
    assert armar_tablero.main(["--destino", str(tmp_path)]) == 0
    texto = (tmp_path / "VERIFICACION.md").read_text()
    assert "Veredicto: LISTO" in texto
    assert (tmp_path / f"{armar_tablero.NOMBRE}.pbit").is_file()
