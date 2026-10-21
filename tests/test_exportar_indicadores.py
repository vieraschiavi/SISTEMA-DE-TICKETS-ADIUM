from tickets_ec import catalogos as C
from tickets_ec import demo, exportar
from tickets_ec import indicadores as I


def _tablas(m):
    return exportar.tablas(m.db, m.cfg, m.ahora())


def test_la_demo_pasa_por_todos_los_estados(demo_corta):
    t = _tablas(demo_corta)
    estados = {e["Estado"] for e in t["Estados"]}
    assert {C.NUEVO, C.ASIGNADO, C.EN_CURSO, C.EN_ESPERA, C.RESUELTO, C.CERRADO, C.CANCELADO} <= estados
    assert {x["Equipo resolutor"] for x in t["Tickets"]} == set(C.EQUIPOS)
    assert {x["Conformidad"] for x in t["Tickets"]} >= {C.CONFORME, C.TACITA}


def test_la_demo_es_reproducible():
    from datetime import datetime
    a = demo.generar(hasta=datetime(2025, 5, 20))
    b = demo.generar(hasta=datetime(2025, 5, 20))
    assert [t["asunto"] for t in a.db.tickets()] == [t["asunto"] for t in b.db.tickets()]


def test_la_demo_no_trae_correos_de_personas_reales(demo_corta):
    for p in demo_corta.db.consulta("SELECT mail FROM personas"):
        assert p["mail"].endswith("@" + demo.DOMINIO)


def test_kpis_cierran(demo_corta):
    t = _tablas(demo_corta)
    k = I.kpis(t["Tickets"], t["Encuestas"])
    assert k["Tickets recibidos"] == len(t["Tickets"])
    for nombre, v in k.items():
        if nombre.startswith("%") or nombre in ("Tasa de reapertura", "Índice de efectividad"):
            assert v is None or 0 <= v <= 1, nombre
    mensual = I.mensual(t["Tickets"], t["Encuestas"], t["Calendario"])
    assert sum(m["Tickets recibidos"] for m in mensual) == k["Tickets recibidos"]
    assert sum(m["Tickets resueltos"] for m in mensual) == k["Tickets resueltos"]
    por_equipo = I.por(t["Tickets"], t["Encuestas"], "Equipo resolutor")
    assert sum(p["Tickets recibidos"] for p in por_equipo) == k["Tickets recibidos"]


def test_backlog_es_lo_que_entro_menos_lo_que_salio(demo_corta):
    t = _tablas(demo_corta)
    k = I.kpis(t["Tickets"], t["Encuestas"])
    salieron = sum(1 for x in t["Tickets"] if x["Fecha salida backlog"] is not None)
    assert k["Backlog fin de período"] == k["Tickets recibidos"] - salieron


def test_tabla_tickets_tiene_las_columnas_del_tablero(demo_corta):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "powerbi"))
    import medidas as MD
    t = _tablas(demo_corta)
    usadas = set()
    for p in MD.PAGINAS:
        usadas |= {c for tabla, c in p.get("filtros", []) if tabla == "Tickets"}
        for fila in p["filas"]:
            for pieza in fila["piezas"]:
                por = pieza.get("por")
                for tabla, c in ([por] if isinstance(por, tuple) else por or []):
                    if tabla == "Tickets":
                        usadas.add(c)
    assert usadas <= set(t["Tickets"][0]), usadas - set(t["Tickets"][0])
    nombres = {m["nombre"] for m in MD.MEDIDAS}
    k = I.kpis(t["Tickets"], t["Encuestas"])
    for m in MD.MEDIDAS:
        assert m["descripcion"], f"{m['nombre']} sin descripción (R24)"
        if m.get("kpi"):
            assert m["kpi"] in k
    for p in MD.PAGINAS:
        for fila in p["filas"]:
            for pieza in fila["piezas"]:
                for n in [pieza.get("medida"), *(pieza.get("medidas") or [])]:
                    assert n is None or n in nombres, n
