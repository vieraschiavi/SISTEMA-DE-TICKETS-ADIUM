import sys
from datetime import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tickets_ec import demo  # noqa: E402
from tickets_ec.almacen import Almacen  # noqa: E402
from tickets_ec.config import Config  # noqa: E402
from tickets_ec.servicio import Mesa  # noqa: E402

SIN_DIRECTORIO = Path("/no-existe/directorio.csv")


class Reloj:
    def __init__(self, inicio: datetime):
        self.ahora = inicio

    def __call__(self):
        return self.ahora

    def avanzar(self, **kw):
        from datetime import timedelta
        self.ahora += timedelta(**kw)


@pytest.fixture
def reloj():
    return Reloj(datetime(2026, 10, 19, 10, 0))      # lunes


@pytest.fixture
def cfg(tmp_path):
    return Config(directorio=SIN_DIRECTORIO, carpeta_adjuntos=tmp_path / "adjuntos",
                  carpeta_salida=tmp_path / "salida")


@pytest.fixture
def mesa(cfg, reloj):
    m = Mesa(Almacen(":memory:"), cfg, reloj=reloj)
    m.alta_analista("ana@adium.com.uy", "Ana", equipo="Excelencia Comercial")
    m.alta_analista("eli@adium.com.uy", "Eli", equipo="Digital")
    m.alta_analista("coord@adium.com.uy", "Coord", coordinador=True)
    return m


@pytest.fixture(scope="session")
def demo_corta():
    """Dos meses de demo: lo bastante para cada estado, rápido para la suite."""
    return demo.generar(hasta=datetime(2025, 7, 1, 12, 0))
