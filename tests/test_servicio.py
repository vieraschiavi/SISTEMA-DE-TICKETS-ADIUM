import pytest

from tickets_ec import catalogos as C
from tickets_ec import correo as CO
from tickets_ec.servicio import ErrorMesa

ANA, ELI = "ana@adium.com.uy", "eli@adium.com.uy"


def _mail(asunto="Necesito el share de pantoprazol", mid="<a1@x>", de="juan@adium.com.ar", cuerpo="IQVIA TAM"):
    return CO.Mensaje(mid, de, "Juan Gómez", asunto, cuerpo, None)


def test_ciclo_completo_con_espera_reapertura_y_tacita(mesa, reloj):
    r = mesa.procesar_correo(_mail())
    assert r.resultado == "nuevo"
    t = mesa.db.ticket(r.numero)
    assert (t["tipo"], t["atc"], t["mercado"], t["area_terapeutica"]) == (
        "Pedido de información", "A02B2", "PANTOPRAZOL", "Aparato Digestivo")
    assert t["pais"] == "Argentina" and t["equipo"] == "Excelencia Comercial"
    assert t["unidad_negocio"] == "Gastro + Hipercol."
    reloj.avanzar(hours=1)
    mesa.asignar(r.numero, ANA, "coord@adium.com.uy")
    reloj.avanzar(hours=1)
    mesa.tomar(r.numero, ANA)
    reloj.avanzar(hours=1)
    mesa.pedir_informacion(r.numero, "¿Qué país?", ANA)
    reloj.avanzar(days=1)
    resp = mesa.procesar_correo(_mail(f"RE: [{r.numero}] Necesito", "<a2@x>", cuerpo="Uruguay"))
    assert resp.resultado == "respuesta"
    assert mesa.db.ticket(r.numero)["estado"] == C.EN_CURSO       # contestó: el reloj sigue
    reloj.avanzar(hours=2)
    t = mesa.resolver(r.numero, "Te mandé el Excel", ANA)
    reloj.avanzar(hours=1)
    t = mesa.responder_encuesta(t["_token"], False, 2, "falta Uruguay")
    assert (t["estado"], t["reaperturas"], t["conformidad"]) == (C.REABIERTO, 1, C.NO_CONFORME)
    reloj.avanzar(hours=1)
    mesa.tomar(r.numero, ANA)
    t = mesa.resolver(r.numero, "Agregado", ANA)
    reloj.avanzar(days=6)
    assert mesa.cierre_tacito() == [r.numero]
    t = mesa.db.ticket(r.numero)
    assert (t["estado"], t["subestado"], t["conformidad"]) == (C.CERRADO, "Conformidad tácita", C.TACITA)
    # 3 h el lunes + 2 h el martes + 1 h reabierto: la espera y el «Resuelto» del medio no cuentan.
    assert mesa.estado_sla(t)["horas_efectivas"] == 6
    assert t["primera_respuesta_en"] is not None


def test_el_analista_no_cierra_lo_que_decide_el_solicitante(mesa):
    t = mesa.crear("Acceso al tablero OLE", "", "x@adium.com.uy", "X")
    mesa.tomar(t["numero"], ANA)
    mesa.resolver(t["numero"], "Listo", ANA)
    with pytest.raises(ErrorMesa, match="no se pasa"):
        mesa.cambiar_estado(t["numero"], C.CERRADO, ANA)


def test_la_encuesta_se_responde_una_vez_y_con_token_valido(mesa):
    t = mesa.crear("Acceso al tablero OLE", "", "x@adium.com.uy", "X")
    mesa.tomar(t["numero"], ANA)
    token = mesa.resolver(t["numero"], "Listo", ANA)["_token"]
    with pytest.raises(ErrorMesa, match="no es válido"):
        mesa.responder_encuesta(token + "x", True, 5)
    with pytest.raises(ErrorMesa, match="Contanos"):
        mesa.responder_encuesta(token, False, 1, "")
    mesa.responder_encuesta(token, True, 5)
    with pytest.raises(ErrorMesa, match="ya se respondió"):
        mesa.responder_encuesta(token, True, 5)
    assert mesa.db.ticket(t["numero"])["csat"] == 5
    assert mesa.db.encuestas()[0]["token_hash"] != token      # se guarda el hash, no el token


def test_correos_automaticos_propios_y_duplicados_no_abren_tickets(mesa):
    assert mesa.procesar_correo(_mail()).resultado == "nuevo"
    assert mesa.procesar_correo(_mail()).resultado == "ignorado: ya procesado"
    propio = _mail(mid="<b@x>", de=mesa.cfg.casilla)
    assert "propia casilla" in mesa.procesar_correo(propio).resultado
    oof = _mail(mid="<c@x>")
    oof.automatico = "Auto-Submitted: auto-replied"
    assert "automática" in mesa.procesar_correo(oof).resultado
    assert len(mesa.db.tickets()) == 1


def test_responder_un_ticket_cerrado_abre_uno_nuevo_que_lo_nombra(mesa):
    t = mesa.crear("Pedido", "", "x@adium.com.uy", "X")
    mesa.cancelar(t["numero"], "Duplicado", ANA, subestado="Duplicado")
    r = mesa.procesar_correo(_mail(f"RE: [{t['numero']}] Pedido", "<z@x>", de="x@adium.com.uy"))
    assert r.resultado == "nuevo" and r.numero != t["numero"]
    assert t["numero"] in mesa.db.ticket(r.numero)["descripcion"]


def test_digital_se_deriva_solo_y_asignar_a_otro_equipo_es_derivar(mesa):
    t = mesa.crear("Mailing de lanzamiento por Veeva", "", "x@adium.com.uy", "X")
    assert t["equipo"] == "Digital" and t["tipo"] == "Pedido digital"
    assert mesa.sugerir_analista("Digital") == ELI
    t2 = mesa.crear("Cambiar filtro del tablero", "", "x@adium.com.uy", "X")
    mesa.asignar(t2["numero"], ELI, "coord@adium.com.uy")
    assert mesa.db.ticket(t2["numero"])["equipo"] == "Digital"
    mesa.derivar(t2["numero"], "Excelencia Comercial", ELI, "es de BI")
    t2 = mesa.db.ticket(t2["numero"])
    assert t2["equipo"] == "Excelencia Comercial" and t2["analista_mail"] is None


def test_el_formulario_manda_sobre_el_clasificador(mesa):
    t = mesa.crear("Algo", "texto", "x@adium.com.uy", "X", canal="Portal", tipo="Nuevo desarrollo",
                   subtipo="Presentación o mazo", atc="A10", prioridad="Baja")
    assert (t["tipo"], t["subtipo"], t["prioridad"], t["area_terapeutica"]) == (
        "Nuevo desarrollo", "Presentación o mazo", "Baja", "Metab & Obesidad")


def test_reclasificar_valida_y_recalcula_area_terapeutica(mesa):
    t = mesa.crear("Algo", "", "x@adium.com.uy", "X")
    with pytest.raises(ErrorMesa):
        mesa.reclasificar(t["numero"], ANA, area="Área inventada")
    t = mesa.reclasificar(t["numero"], ANA, atc="C10", area="Marketing")
    assert t["area_terapeutica"] == "Cardiovascular"
    assert mesa.db.persona("x@adium.com.uy")["area"] == "Marketing"      # el próximo ya viene bien


def test_acuse_y_encuesta_escapan_lo_que_escribe_el_solicitante(mesa):
    mesa.crear("<script>alert(1)</script>", "", "x@adium.com.uy", "<b>X</b>")
    html = mesa.salida.enviados[-1].get_body(("html",)).get_content()
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_pedir_informacion_y_cancelar_piden_texto(mesa):
    t = mesa.crear("Algo", "", "x@adium.com.uy", "X")
    with pytest.raises(ErrorMesa):
        mesa.pedir_informacion(t["numero"], " ", ANA)
    with pytest.raises(ErrorMesa):
        mesa.cancelar(t["numero"], "", ANA)
    with pytest.raises(ErrorMesa):
        mesa.resolver(t["numero"], "", ANA)


def test_las_columnas_se_validan(mesa):
    t = mesa.crear("Algo", "", "x@adium.com.uy", "X")
    with pytest.raises(ValueError, match="no tiene"):
        mesa.db.actualizar_ticket(t["id"], **{"estado = 'Cerrado'; --": 1})
