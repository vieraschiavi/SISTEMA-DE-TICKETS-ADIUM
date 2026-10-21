from tickets_ec import guia


def test_cada_paso_apunta_a_secciones_y_archivos_que_existen():
    for p in guia.PASOS:
        for documento, prefijo in p.secciones:
            assert guia.seccion(documento, prefijo), f"{p.clave}: no hay sección «{prefijo}» en {documento}"
        for a in p.archivos:
            if not a.startswith("powerbi/Tickets_"):          # el tablero se arma aparte
                assert guia.archivo(a).is_file(), a


def test_claves_unicas_y_los_seis_flujos():
    assert len({p.clave for p in guia.PASOS}) == len(guia.PASOS)
    flujos = next(p for p in guia.PASOS if p.clave == "flujos")
    assert len(flujos.secciones) == 6
