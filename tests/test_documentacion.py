"""La documentación del proyecto (docs/PROYECTO.md y .html) es la que genera el programa, y está al día."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import documentar as D  # noqa: E402

from tickets_ec import __version__  # noqa: E402
from tickets_ec import catalogos as C  # noqa: E402


def test_lo_commiteado_es_lo_que_genera_el_programa():
    for ruta, contenido in D.archivos().items():
        assert ruta.read_text(encoding="utf-8") == contenido, (
            f"{ruta.name} quedó viejo: corré python scripts/documentar.py (y sumá la entrada en docs/CAMBIOS.md)")


def test_la_version_del_historial_es_la_del_programa():
    assert D.version_documentada() == __version__, "docs/CAMBIOS.md no tiene la entrada de esta versión"


def test_cada_canal_dice_como_entra():
    assert set(D.CANALES) == set(C.CANALES)


def test_el_html_se_lee_solo_y_escapa_lo_que_muestra():
    pagina = (RAIZ / "docs" / "PROYECTO.html").read_text(encoding="utf-8")
    assert "<script" not in pagina and "http://" not in pagina and "https://" not in pagina   # sin nada externo
    assert D._en_linea("<b>**ok**</b>") == "&lt;b&gt;<strong>ok</strong>&lt;/b&gt;"
