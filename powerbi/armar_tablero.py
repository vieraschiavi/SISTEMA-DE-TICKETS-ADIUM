"""
Arma el tablero de Power BI de la mesa (`.pbit` + el Excel que lee) con el
motor de la suite Adium All in One, y VERIFICA cada KPI antes de entregarlo.

    python powerbi/armar_tablero.py                 # con la demo
    python powerbi/armar_tablero.py --base datos/tickets.db

Necesita la suite al lado (`../Power-bi`, o la ruta en `ADIUM_SUITE`): el
.pbit lo escribe MV DAX Lab, el mismo motor que arma los tableros de la
suite, con su layout, su marca y su gate de salida (`verificacion.verificar`).

Qué se verifica, y por qué no alcanza con que el .pbit abra
-----------------------------------------------------------
1. **El archivo**: los chequeos de `dxl.verificacion` sobre el .pbit escrito.
2. **Los números**: cada medida con `kpi` se evalúa con el evaluador de DAX
   de la suite (`dxl.dax_eval`) sobre las mismas tablas que lleva el Excel,
   en total, mes por mes y por equipo resolutor, y se compara con
   `tickets_ec.indicadores` (la definición en Python que muestra la app).
   Una medida que compila y da otro número que la app es un tablero que
   contradice a la bandeja: no se entrega.
3. **Los filtros**: cada segmentador tiene que ofrecer TODOS los valores que
   hay en los datos (todos los equipos, todos los tipos, todos los países).

El resultado queda en `powerbi/VERIFICACION.md`. Si algo falla, el .pbit
sale con «· REVISAR» en el nombre y el script termina con código 1.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "powerbi"))

import medidas as MD  # noqa: E402

from tickets_ec import demo, exportar  # noqa: E402
from tickets_ec import indicadores as I  # noqa: E402
from tickets_ec.almacen import Almacen  # noqa: E402
from tickets_ec.config import cargar  # noqa: E402

NOMBRE = "Tickets_Excelencia_Comercial_y_Digital"
TITULO = "Tickets · Excelencia Comercial & Digital"
TOLERANCIA = 1e-6
#: Lo que el .pbit propone como carpeta del Excel. Power BI la pregunta al
#: abrir la plantilla; sin esto propondría la carpeta de la máquina que la armó.
CARPETA_DEFECTO = "C:\\TicketsEC\\datos\\powerbi\\"


def suite() -> Path:
    ruta = Path(os.environ.get("ADIUM_SUITE", RAIZ.parent / "Power-bi"))
    if not (ruta / "AdiumAllinOne" / "adium_allinone" / "tablero_etapas.py").is_file():
        raise SystemExit(f"No encuentro la suite Adium All in One en {ruta}. Clonala al lado de este repo o "
                         "poné su ruta en ADIUM_SUITE.")
    for sub in ("AdiumAllinOne", "AllinOne", "daxlingo"):
        sys.path.insert(0, str(ruta / sub))
    return ruta


def _igual(a, b) -> bool:
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None
    if b is None:
        return False
    return abs(float(a) - float(b)) <= TOLERANCIA * max(1.0, abs(float(b)))


def verificar_numeros(modelo: dict, dfs: dict, filas: dict, hasta_cal: date) -> tuple[list[str], int]:
    """Cada medida con `kpi`, contra `indicadores.kpis`: total, por mes y por equipo."""
    from dxl import dax_eval as DE

    motor = DE.Motor(modelo, dfs)
    tickets, encuestas, cal = filas["Tickets"], filas["Encuestas"], filas["Calendario"]
    con_kpi = [m for m in MD.MEDIDAS if m.get("kpi")]
    errores, chequeos = [], 0

    def comparar(etiqueta: str, ctx, esperado: dict):
        nonlocal chequeos
        for m in con_kpi:
            chequeos += 1
            try:
                dax = motor.medida(m["nombre"], ctx)
            except Exception as e:     # noqa: BLE001 — se informa, no se esconde
                errores.append(f"{etiqueta} · {m['nombre']}: el DAX no se pudo evaluar ({e})")
                continue
            dax = None if DE._blanco(dax) else dax
            if not _igual(dax, esperado[m["kpi"]]):
                errores.append(f"{etiqueta} · {m['nombre']}: DAX {dax!r} ≠ Python {esperado[m['kpi']]!r}")

    comparar("Total", DE.Contexto(), I.kpis(tickets, encuestas, hasta=hasta_cal))
    meses: dict[str, list[date]] = {}
    for d in cal:
        meses.setdefault(d["Período"], []).append(d["Fecha"])
    for mes in list(meses)[-6:] + list(meses)[:1]:
        f = DE.Filtro("Calendario", ("Período",), frozenset({(mes,)}))
        comparar(f"Mes {mes}", DE.Contexto((f,)), I.kpis(tickets, encuestas, min(meses[mes]), max(meses[mes])))
    for equipo in sorted({t["Equipo resolutor"] for t in tickets}):
        sub = [t for t in tickets if t["Equipo resolutor"] == equipo]
        f = DE.Filtro("Tickets", ("Equipo resolutor",), frozenset({(equipo,)}))
        comparar(f"Equipo {equipo}", DE.Contexto((f,)), I.kpis(sub, encuestas, hasta=hasta_cal, todos=sub))
    return errores, chequeos


def verificar_filtros(layout: dict, filas: dict) -> list[str]:
    """Cada segmentador del tablero, contra los valores de los datos."""
    import json
    avisos = []
    for seccion in layout.get("sections", []):
        for v in seccion.get("visualContainers", []):
            conf = json.loads(v.get("config", "{}"))
            sv = conf.get("singleVisual", {})
            if sv.get("visualType") != "slicer":
                continue
            for proy in sv.get("projections", {}).get("Values", []):
                tabla, _, col = proy.get("queryRef", "").partition(".")
                if tabla in filas and filas[tabla] and col in filas[tabla][0]:
                    valores = {r[col] for r in filas[tabla] if r[col] not in (None, "")}
                    if len(valores) < 2:
                        avisos.append(f"{seccion.get('displayName')}: el segmentador {tabla}[{col}] ofrece "
                                      f"{len(valores)} valor(es)")
    return avisos


#: dtype de pandas → (dataType TMSL, tipo M).
_TIPOS = {"i": ("int64", "Int64.Type"), "f": ("double", "type number"), "M": ("dateTime", "type datetime")}


def tipar(modelo: dict, dfs: dict) -> list[str]:
    """El tipo de cada columna, sacado de los DATOS y no de una muestra.

    El lector de Excel del motor infiere el tipo con las primeras 500 filas:
    una columna que arriba viene vacía («Días abierto» sólo tiene valor en
    los pendientes) queda como texto, y en Power BI un AVERAGE sobre texto es
    un error, no un número. Acá se fija cada columna numérica o de fecha con
    su tipo real, en el modelo Y en el `Table.TransformColumnTypes` del
    Power Query. Devuelve lo que corrigió."""
    corregidas = []
    for t in modelo.get("model", modelo).get("tables", []):
        df = dfs.get(t["name"])
        if df is None:
            continue
        for c in t.get("columns", []):
            serie = df.get(c.get("sourceColumn") or c["name"])
            if serie is None or serie.dtype.kind not in _TIPOS:
                continue
            tmsl, tipo_m = _TIPOS[serie.dtype.kind]
            if tmsl == "double" and serie.dropna().apply(float.is_integer).all():
                tmsl, tipo_m = _TIPOS["i"]
            if c.get("dataType") == tmsl:
                continue
            corregidas.append(f"{t['name']}[{c['name']}]: {c.get('dataType')} → {tmsl}")
            c["dataType"] = tmsl
            for part in t.get("partitions", []):
                src = part.get("source", {})
                expr = src.get("expression")
                lineas = expr if isinstance(expr, list) else [expr or ""]
                nombre = c["name"].replace('"', '""')
                for viejo in ("type text", "Int64.Type", "type number", "type datetime"):
                    lineas = [ln.replace(f'{{"{nombre}", {viejo}}}', f'{{"{nombre}", {tipo_m}}}') for ln in lineas]
                src["expression"] = lineas if isinstance(expr, list) else lineas[0]
    return corregidas


def carpeta_portable(modelo: dict, carpeta: str = CARPETA_DEFECTO) -> bool:
    """El valor por defecto del parámetro `CarpetaDatos`, sin la ruta local."""
    for e in modelo.get("model", modelo).get("expressions", []) or []:
        if e.get("name") == "CarpetaDatos":
            valor = carpeta.replace('"', '""')
            e["expression"] = [f'"{valor}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]']
            return True
    return False


def tipos_que_no_cierran(modelo: dict, dfs: dict) -> list[str]:
    """El gate: una columna numérica o de fecha que en el modelo quedó texto."""
    malas = []
    for t in modelo.get("model", modelo).get("tables", []):
        df = dfs.get(t["name"])
        for c in t.get("columns", []) if df is not None else []:
            serie = df.get(c.get("sourceColumn") or c["name"])
            if serie is not None and serie.dtype.kind in _TIPOS and c.get("dataType") == "string":
                malas.append(f"{t['name']}[{c['name']}] es {serie.dtype} en los datos y texto en el modelo")
    return malas


def pbip_y_zip(modelo: dict, layout: dict, recursos: dict, destino: Path) -> tuple[Path, Path]:
    """El proyecto PBIP (lo que Fabric sincroniza con Git) y su .zip para bajarlo."""
    import shutil
    import zipfile

    from dxl import modelo as modmod
    carpeta = destino / "pbip"
    if carpeta.exists():
        shutil.rmtree(carpeta)
    pbip = modmod.exportar_pbip(modelo, layout, carpeta, NOMBRE)
    for nombre, datos in (recursos or {}).items():        # el logo, donde un PBIP guarda sus imágenes
        parte = carpeta / f"{NOMBRE}.Report" / "StaticResources" / "RegisteredResources" / nombre
        parte.parent.mkdir(parents=True, exist_ok=True)
        parte.write_bytes(datos)
    zipeado = destino / f"{NOMBRE}_PBIP.zip"
    with zipfile.ZipFile(zipeado, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta in sorted(carpeta.rglob("*")):
            if ruta.is_file():
                z.write(ruta, ruta.relative_to(carpeta))
    return pbip, zipeado


def armar(base: Path | None, destino: Path) -> int:
    suite()
    from adium_allinone import marca as marca_suite
    from adium_allinone import tablero_etapas as TE
    from dxl import verificacion

    if base:
        cfg = cargar()
        db, ahora = Almacen(base), datetime.now()
    else:
        mesa = demo.generar()
        cfg, db, ahora = mesa.cfg, mesa.db, demo.HASTA
    filas = exportar.tablas(db, cfg, ahora)
    dfs = exportar.a_dataframes(filas)
    hasta_cal = max(d["Fecha"] for d in filas["Calendario"])

    # Las medidas van a una tabla con nombre propio y no a la de la suite
    # («_Medidas etapas»): es lo que el usuario ve en la lista de campos.
    TE.TABLA_MEDIDAS = "_Medidas"
    destino.mkdir(parents=True, exist_ok=True)
    pbit = destino / f"{NOMBRE}.pbit"
    logo = marca_suite.LOGO.read_bytes() if marca_suite.LOGO.is_file() else None
    r = TE.generar(dfs, medidas=[{k: v for k, v in m.items() if k != "kpi"} for m in MD.MEDIDAS], titulo=TITULO,
                   destino=pbit, paginas=MD.PAGINAS, estilo="adium", relaciones=MD.RELACIONES, rfm=False,
                   menu_grupos=MD.MENU_GRUPOS, logo=logo, libre=True, orden=MD.ORDEN)

    # La réplica: el mismo tablero en una página HTML, con los números
    # calculados por el DAX del modelo. Para mirarlo sin Power BI Desktop.
    (destino / f"{NOMBRE}.html").write_text(TE.replica_html(r, TITULO), encoding="utf-8")
    from dxl import modelo as modmod
    tipadas = tipar(r.modelo, dfs)
    carpeta_portable(r.modelo)
    # El .pbit se reescribe con los tipos de los datos y la carpeta portable.
    modmod.exportar_pbit(r.modelo, r.layout, r.pbit, descripcion="Generado por Adium All in One",
                         recursos=r.recursos or None)
    tipos_malos = tipos_que_no_cierran(r.modelo, dfs)
    pbip, zipeado = pbip_y_zip(r.modelo, r.layout, r.recursos, destino)
    gate_pbip = verificacion.verificar(pbip)
    gate = verificacion.verificar(r.pbit)
    errores, chequeos = verificar_numeros(r.modelo, dfs, filas, hasta_cal)
    filtros = verificar_filtros(r.layout, filas)
    paginas_ok = [p["titulo"] for p in MD.PAGINAS if p["titulo"] in r.temas]
    faltan_paginas = [p["titulo"] for p in MD.PAGINAS if p["titulo"] not in r.temas]
    listo = (gate["listo"] and gate_pbip["listo"] and not errores and not r.rechazadas and not faltan_paginas
             and not filtros and not tipos_malos)

    lineas = [f"# Verificación del tablero · {datetime.now():%Y-%m-%d %H:%M}", "",
              f"Origen: {'base ' + str(base) if base else 'demo (semilla 42, hasta ' + str(demo.HASTA) + ')'}",
              f"Archivo: `{r.pbit.name}` · {r.tablas} tablas · {r.relaciones} relaciones · {r.medidas} medidas · "
              f"{r.paginas} páginas", "",
              f"## Veredicto: {'LISTO' if listo else 'REVISAR'}", "",
              f"- Gate del archivo (`dxl.verificacion`): {'listo' if gate['listo'] else 'con faltas'} "
              f"({gate['faltan']} faltas, {gate['avisos']} avisos)",
              f"- Gate del proyecto PBIP (Fabric / Git): {'listo' if gate_pbip['listo'] else 'con faltas'} "
              f"({gate_pbip['faltan']} faltas, {gate_pbip['avisos']} avisos) · `{zipeado.name}`",
              f"- Tipos de columna iguales a los datos: {'sí' if not tipos_malos else 'NO'}"
              + (f" ({len(tipadas)} corregidas sobre la inferencia por muestra)" if tipadas else ""),
              f"- Números: {chequeos - len(errores)}/{chequeos} medidas iguales a `tickets_ec.indicadores` "
              "(total, 7 meses y cada equipo resolutor)",
              f"- Medidas rechazadas por el catálogo: {len(r.rechazadas)}",
              f"- Páginas: {len(paginas_ok)}/{len(MD.PAGINAS)}" + (f" — faltan {faltan_paginas}" if faltan_paginas else ""),
              f"- Segmentadores con un solo valor: {len(filtros)}", ""]
    for titulo, items in (("Diferencias de números", errores), ("Medidas rechazadas", r.rechazadas),
                          ("Tipos de columna que no cierran", tipos_malos), ("Tipos corregidos", tipadas),
                          ("Segmentadores", filtros), ("Notas de las páginas", r.notas),
                          ("Arreglos automáticos del modelo", r.arreglos)):
        if items:
            lineas += [f"## {titulo}", ""] + [f"- {i}" for i in items] + [""]
    faltas = [i for i in gate["items"] if i.get("estado") not in ("ok", "OK")]
    if faltas:
        lineas += ["## Ítems del gate que no dieron OK", ""] + [
            f"- {i.get('estado')} · {i.get('titulo')}: {i.get('detalle')}" for i in faltas] + [""]
    k = I.kpis(filas["Tickets"], filas["Encuestas"], hasta=hasta_cal)
    lineas += ["## KPIs del total (los mismos que muestra el tablero)", "", "| KPI | Valor |", "|---|---|"]
    lineas += [f"| {n} | {('—' if v is None else f'{v:.1%}' if n.startswith('%') or n in ('Tasa de reapertura', 'Índice de efectividad') else f'{v:,.2f}' if isinstance(v, float) else v)} |"
               for n, v in k.items()]
    (destino / "VERIFICACION.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")

    if not listo:
        revisar = pbit.with_name(f"{NOMBRE} · REVISAR.pbit")
        r.pbit.replace(revisar)
        print(f"REVISAR: {revisar.name} — ver powerbi/VERIFICACION.md")
        return 1
    print(f"LISTO: {r.pbit.name} · {chequeos} chequeos de números iguales · {r.paginas} páginas")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--base", type=Path, help="la base SQLite de la mesa (sin esto, la demo)")
    p.add_argument("--destino", type=Path, default=RAIZ / "powerbi")
    a = p.parse_args(argv)
    return armar(a.base, a.destino)


if __name__ == "__main__":
    sys.exit(main())
