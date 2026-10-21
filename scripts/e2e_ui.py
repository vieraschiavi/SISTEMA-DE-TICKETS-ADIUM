"""E2E de la app en Chromium: levanta la app de verdad, recorre cada página y
falla si alguna muestra una excepción. Lo que pytest no ve.

    TICKETS_CHROMIUM=/opt/pw-browsers/chromium-*/chrome-linux/chrome python scripts/e2e_ui.py [carpeta-capturas]

Usa la base de `datos/tickets.db` (cargá la demo antes: `python -m tickets_ec.demo`).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PUERTO = 8761
PAGINAS = ["Inicio", "Bandeja", "Ticket", "Nuevo pedido", "Casilla", "Indicadores", "Power BI", "Configuración"]


def main() -> int:
    from playwright.sync_api import sync_playwright
    capturas = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    exe = os.environ.get("TICKETS_CHROMIUM") or next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")), None)
    app = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/app.py", "--server.headless", "true",
                            "--server.port", str(PUERTO)], cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    fallas = []
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/_stcore/health", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            pg = b.new_page(viewport={"width": 1440, "height": 1000})
            pg.goto(f"http://127.0.0.1:{PUERTO}/?ticket=EC-00042")
            pg.wait_for_selector("[data-testid=stSidebar]", timeout=60000)
            for nombre in PAGINAS:
                pg.locator("[data-testid=stSidebar] label").filter(has_text=nombre).first.click()
                pg.wait_for_timeout(2500)
                pg.wait_for_selector("[data-testid=stStatusWidget]", state="detached", timeout=60000)
                errores = pg.locator("[data-testid=stException]").count()
                print(f"{'FALLA' if errores else 'ok   '} {nombre}")
                if errores:
                    fallas.append(f"{nombre}: {pg.locator('[data-testid=stException]').first.inner_text()[:400]}")
                if capturas:
                    capturas.mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=str(capturas / f"{nombre}.png"), full_page=True)
            b.close()
    finally:
        app.terminate()
    for f in fallas:
        print(f)
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
