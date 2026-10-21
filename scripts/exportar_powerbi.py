"""Exporta el modelo estrella que lee el tablero (Excel + un CSV por tabla).

    python scripts/exportar_powerbi.py                       # desde la base SQLite de la mesa
    python scripts/exportar_powerbi.py --origen sharepoint   # desde las listas de Power Platform (Graph)
    python scripts/exportar_powerbi.py --origen carpeta --csv <carpeta>   # desde los CSV del flujo 6

Con `--origen sharepoint` lee las listas por Microsoft Graph (permiso
`Sites.Selected`, sólo lectura) y calcula horas hábiles, reloj detenido y
SLA con el mismo código que la app. Es lo que corre una vez por día, antes
de la actualización programada del modelo en el servicio de Power BI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tickets_ec import exportar, sharepoint  # noqa: E402
from tickets_ec.almacen import Almacen  # noqa: E402
from tickets_ec.config import cargar  # noqa: E402

NOMBRE = "Tickets_Excelencia_Comercial_y_Digital.xlsx"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--origen", choices=("sqlite", "sharepoint", "carpeta"), default="sqlite")
    p.add_argument("--csv", type=Path, help="con --origen carpeta: donde el flujo 6 deja los CSV de las listas")
    p.add_argument("--carpeta", type=Path, default=RAIZ / "datos" / "powerbi")
    a = p.parse_args(argv)
    cfg = cargar()
    if a.origen == "sharepoint":
        if not cfg.sharepoint_host:
            raise SystemExit("Falta sharepoint_host en config.toml (p. ej. «adium.sharepoint.com»).")
        cliente = sharepoint.ClienteGraph(cfg.graph_tenant, cfg.graph_cliente, cfg.graph_secreto)
        db = sharepoint.cargar(cliente, cliente.sitio(cfg.sharepoint_host, cfg.sharepoint_sitio))
    elif a.origen == "carpeta":
        if not a.csv:
            raise SystemExit("--origen carpeta necesita --csv <carpeta con Tickets.csv, Eventos.csv…>")
        db = sharepoint.cargar(sharepoint.ClienteCarpeta(a.csv))
    else:
        db = Almacen(cfg.base)
    t = exportar.tablas(db, cfg)
    exportar.a_csv(t, a.carpeta)
    import pandas as pd
    with pd.ExcelWriter(a.carpeta / NOMBRE) as w:
        for nombre, df in exportar.a_dataframes(t).items():
            df.to_excel(w, sheet_name=nombre, index=False)
    print(f"{len(t['Tickets'])} tickets → {a.carpeta / NOMBRE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
