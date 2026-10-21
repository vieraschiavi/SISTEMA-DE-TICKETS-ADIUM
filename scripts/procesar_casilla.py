"""Lee la casilla, registra cada correo y corre los cierres tácitos.

    python scripts/procesar_casilla.py

Es lo que corre el Programador de tareas de Windows cada 5 minutos
(`scripts/procesar_casilla.bat`). Un solo proceso a la vez: si la corrida
anterior sigue, ésta sale sin hacer nada (archivo de bloqueo).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tickets_ec import correo as CO  # noqa: E402
from tickets_ec.almacen import Almacen  # noqa: E402
from tickets_ec.config import cargar  # noqa: E402
from tickets_ec.servicio import Mesa  # noqa: E402


def fuente(cfg):
    if cfg.fuente == "graph":
        return CO.FuenteGraph(cfg.graph_tenant, cfg.graph_cliente, cfg.graph_secreto, cfg.casilla)
    if cfg.fuente == "imap":
        return CO.FuenteIMAP(cfg.imap_host, cfg.imap_usuario, clave=cfg.imap_clave)
    return CO.FuenteCarpeta(cfg.carpeta_entrada)


def main() -> int:
    cfg = cargar()
    candado = Path(cfg.base).with_suffix(".lock")
    try:
        fd = os.open(candado, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"{datetime.now():%H:%M} otra corrida en curso ({candado.name}); salgo.")
        return 0
    try:
        os.write(fd, str(os.getpid()).encode())
        enviar = None
        if cfg.envio_activo:
            enviar = (CO.enviador_smtp(cfg.smtp_host, cfg.smtp_puerto, cfg.casilla, cfg.smtp_clave)
                      if cfg.envio == "smtp" else
                      CO.FuenteGraph(cfg.graph_tenant, cfg.graph_cliente, cfg.graph_secreto, cfg.casilla).enviar)
        mesa = Mesa(Almacen(cfg.base), cfg, CO.BuzonSalida(cfg.carpeta_salida, enviar))
        resultados = mesa.procesar_bandeja(fuente(cfg))
        tacitos = mesa.cierre_tacito()
        errores = [r for r in resultados if r.resultado.startswith("error")]
        print(f"{datetime.now():%Y-%m-%d %H:%M} · {len(resultados)} correos · {len(errores)} con error · "
              f"{len(tacitos)} cierres tácitos")
        for r in errores:
            print(f"  {r.message_id}: {r.resultado}")
        return 1 if errores else 0
    finally:
        os.close(fd)
        candado.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
