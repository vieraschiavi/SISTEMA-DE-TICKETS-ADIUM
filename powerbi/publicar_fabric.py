"""
Publica el tablero en un workspace de Microsoft Fabric / Power BI Service por
la API REST (modelo semántico + reporte), con el motor de la suite
(`dxl.fabric.publicar`).

    # el token es del usuario y NO se guarda: vive en la variable de entorno
    export TICKETS_FABRIC_TOKEN=$(az account get-access-token \
        --resource https://api.fabric.microsoft.com --query accessToken -o tsv)
    python powerbi/publicar_fabric.py --workspace <id-del-workspace>
    python powerbi/publicar_fabric.py --ver          # sólo muestra qué mandaría

Después de publicar falta UNA cosa que la API no puede hacer por vos: en el
servicio, en la configuración del modelo semántico, poner el parámetro
`CarpetaDatos` y las credenciales del origen (ver docs/POWERBI.md). Sin eso el
modelo está publicado pero vacío.

Los otros dos caminos no necesitan token:
* Fabric + Git: conectar el workspace a un repo con la carpeta
  `powerbi/pbip/` (formato PBIP); Fabric crea los ítems solo.
* Power BI Desktop: abrir el `.pbit`, «Guardar como» `.pbix` y Publicar.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import armar_tablero  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--workspace", help="id del workspace de Fabric / Power BI")
    p.add_argument("--nombre", default=armar_tablero.TITULO)
    p.add_argument("--ver", action="store_true", help="mostrar lo que se mandaría, sin publicar")
    a = p.parse_args(argv)
    armar_tablero.suite()
    from dxl import fabric
    from dxl import modelo as modmod

    pbit = RAIZ / f"{armar_tablero.NOMBRE}.pbit"
    if not pbit.is_file():
        raise SystemExit("No está el .pbit: corré primero python powerbi/armar_tablero.py")
    cargado = modmod.cargar(str(pbit))
    modelo, layout = cargado["modelo"], cargado["layout"]
    if a.ver:
        carga = fabric.payload_modelo_semantico(a.nombre, modelo)
        print(json.dumps({"modelo_semantico": [x["path"] for x in carga["definition"]["parts"]],
                          "tablas": [t["name"] for t in modelo["model"]["tables"]],
                          "paginas": len(layout.get("sections", []))}, ensure_ascii=False, indent=2))
        return 0
    token = os.environ.get("TICKETS_FABRIC_TOKEN", "")
    if not (a.workspace and token):
        raise SystemExit("Falta --workspace o la variable TICKETS_FABRIC_TOKEN (ver el encabezado de este archivo).")
    r = fabric.publicar(a.workspace, a.nombre, modelo, layout, token)
    print(f"Publicado: modelo semántico {r['modelo_semantico']} · reporte {r['reporte']}")
    print("Falta: parámetro CarpetaDatos y credenciales del origen en la configuración del modelo semántico.")
    return 0 if r.get("modelo_semantico") else 1


if __name__ == "__main__":
    sys.exit(main())
