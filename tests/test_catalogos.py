from tickets_ec import catalogos as C


def test_resuelto_lo_cierra_solo_el_solicitante():
    assert not C.puede(C.RESUELTO, C.CERRADO)
    assert C.puede(C.RESUELTO, C.CERRADO, sistema=True)
    assert C.puede(C.RESUELTO, C.REABIERTO, sistema=True)


def test_finales_no_salen():
    for e in C.FINALES:
        assert not C.TRANSICIONES[e]
        assert e not in C.TRANSICIONES_SISTEMA


def test_cada_estado_tiene_subestado_y_orden():
    for e in C.ESTADOS:
        assert C.SUBESTADOS[e]
        assert e in C.ORDEN_ESTADO


def test_cada_tipo_tiene_subtipo_dias_y_equipo():
    for t in C.TIPOS:
        assert t.subtipos and len(t.dias) == 4 and t.equipo in C.EQUIPOS
        assert list(t.dias) == sorted(t.dias), f"{t.nombre}: la prioridad más alta no puede tener más plazo"
        assert t.prioridad in C.POR_PRIORIDAD


def test_digital_es_equipo_resolutor_y_tiene_su_tipo():
    assert C.EQUIPOS == ("Excelencia Comercial", "Digital")
    assert C.POR_TIPO["Pedido digital"].equipo == "Digital"


def test_area_terapeutica_por_prefijo_mas_largo():
    assert C.area_terapeutica("A10N1") == "Metab & Obesidad"
    assert C.area_terapeutica("G03B") == "Salud del Hombre"
    assert C.area_terapeutica("G03A") == "Salud de la Mujer"
    assert C.area_terapeutica("C10A1") == "Cardiovascular"
    assert C.area_terapeutica("Z99") is None


def test_unidad_de_negocio_no_es_el_area_terapeutica():
    assert (C.area_terapeutica("C10A1"), C.unidad_negocio("C10A1")) == ("Cardiovascular", "Gastro + Hipercol.")
    assert C.unidad_negocio("N03A", "PREGABALINA") == "Osteo Dolor"
    assert C.unidad_negocio("N03A", "LEVETIRACETAM") == "Neurociencias"
    assert C.unidad_negocio("G03B") == "Salud del Hombre" and C.unidad_negocio("G03A") == "Salud de la Mujer"
    assert C.unidad_negocio("") == C.UNIDAD_NEGOCIO_DEFECTO
    assert set(C.UNIDAD_POR_ATC.values()) <= set(C.UNIDADES_NEGOCIO)


def test_la_tabla_de_sla_de_la_documentacion_es_la_del_codigo():
    from pathlib import Path
    doc = (Path(__file__).resolve().parent.parent / "docs" / "INDICADORES.md").read_text(encoding="utf-8")
    for t in C.TIPOS:
        if t.nombre == C.TIPO_DEFECTO:
            continue
        fila = f"| {t.nombre} | " + " | ".join(str(d) for d in t.dias) + f" | {t.equipo} |"
        assert fila in doc, f"docs/INDICADORES.md desactualizado: {fila}"
