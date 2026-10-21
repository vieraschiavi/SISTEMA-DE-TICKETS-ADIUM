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


def test_progreso_y_markdown():
    hechos, total, siguiente = guia.progreso({"it", "listas"})
    assert (hechos, total, siguiente) == (2, len(guia.PASOS), guia.PASOS[2].titulo)
    assert guia.progreso({p.clave for p in guia.PASOS})[2] == ""
    md = guia.a_markdown()
    assert "## 4. Conectar la app de cada integrante a la misma mesa" in md
    assert "## 5. Crear los 6 flujos de Power Automate" in md and "Correo → ticket" in md and "scrDetalle" in md
