"""Arma `tickets_ec/datos/mercados_conformados.csv` desde la definición de HQ
que vive en la suite (`AdiumAllinOne/adium_allinone/datos/mercados_conformados_hq_2025.csv`).

Se guarda sólo lo que la mesa necesita para clasificar un pedido: área
terapéutica, nombre del mercado y sus clases terapéuticas (CT). La definición
completa sigue siendo la de HQ, en la suite.

    python scripts/importar_mercados.py [ruta-al-csv-de-HQ]
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from tickets_ec import catalogos as C  # noqa: E402

SUITE = Path(os.environ.get("ADIUM_SUITE", RAIZ.parent / "Power-bi"))
ORIGEN = SUITE / "AdiumAllinOne" / "adium_allinone" / "datos" / "mercados_conformados_hq_2025.csv"
DESTINO = RAIZ / "tickets_ec" / "datos" / "mercados_conformados.csv"
_CT = re.compile(r"\b([A-Z]\d{2}[A-Z]\d?)\b")
#: Los nombres de área de la hoja de HQ → los del catálogo de la mesa.
#: Las canastas CORE que HQ define por molécula y no por CT: la clase a nivel 2.
SIN_CT = {"LEVOSIMENDAN": "C01", "ROSUVASTATINA": "C10", "MULTIVITAMINICOS": "A11"}
AREAS = {"Neuro": "Neurociencias", "Metabolismo & Obesidad": "Metab & Obesidad",
         "CORE · Metabolismo & Obesidad": "Metab & Obesidad"}


def main(origen: Path = ORIGEN) -> int:
    filas = []
    with open(origen, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cts = list(dict.fromkeys(_CT.findall(r["Definición HQ"].upper())))
            if not cts and r["Mercado"].strip().upper() in SIN_CT:
                cts = [SIN_CT[r["Mercado"].strip().upper()]]
            area = r["Área"].strip()
            if area.startswith("CORE"):        # las canastas CORE cruzan áreas: manda el ATC
                area = C.area_terapeutica(cts[0] if cts else "") or "Otra"
            filas.append({"area_terapeutica": AREAS.get(area, area), "mercado": r["Mercado"].strip(),
                          "atc": cts[0] if cts else "", "cts": " ".join(cts)})
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["area_terapeutica", "mercado", "atc", "cts"])
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} mercados → {DESTINO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ORIGEN))
