"""El portal del solicitante: cada uno ve y toca sólo lo suyo, y lo que hace mueve el ticket como un correo."""
import pytest

from tickets_ec import catalogos as C
from tickets_ec.servicio import ErrorMesa

ANA = "ana@adium.com.uy"
JUAN, PAULA, OTRA = "juan@adium.com.ar", "paula@adium.com.uy", "otra@adium.cl"


def _pedido(mesa, asunto="Necesito el share de pantoprazol", de=JUAN, cc=None):
    return mesa.crear(asunto, "IQVIA MAT", de, "Juan Gómez", canal="Portal", cc=cc or [])


def test_cada_uno_ve_lo_suyo_y_lo_que_lleva_en_copia(mesa):
    a = _pedido(mesa, cc=[PAULA])
    b = _pedido(mesa, "Acceso al tablero de Close Up", de=OTRA)
    assert [t["numero"] for t in mesa.mis_tickets(JUAN)] == [a["numero"]]
    assert [t["numero"] for t in mesa.mis_tickets(PAULA)] == [a["numero"]]
    assert [t["numero"] for t in mesa.mis_tickets(OTRA.upper())] == [b["numero"]]
    with pytest.raises(ErrorMesa, match="no es un pedido tuyo"):
        mesa.conversacion(b["numero"], JUAN)


def test_la_conversacion_no_muestra_lo_interno(mesa):
    t = _pedido(mesa)
    mesa.tomar(t["numero"], ANA)
    mesa.comentar(t["numero"], "Ojo: el cliente es difícil", ANA)               # nota interna
    mesa.comentar(t["numero"], "Te lo mando hoy", ANA, publico=True)
    tipos = [(e["tipo"], e["detalle"]) for e in mesa.conversacion(t["numero"], JUAN)]
    assert ("comentario", "Te lo mando hoy") in tipos
    assert all("difícil" not in d for _t, d in tipos)
    assert all(tp != "correo_saliente" for tp, _d in tipos)


def test_responder_desde_el_portal_saca_el_ticket_de_la_espera(mesa, reloj):
    t = _pedido(mesa)
    mesa.tomar(t["numero"], ANA)
    mesa.pedir_informacion(t["numero"], "¿Qué país?", ANA)
    reloj.avanzar(hours=2)
    with pytest.raises(ErrorMesa, match="no es un pedido tuyo"):
        mesa.responder_como_solicitante(t["numero"], "Uruguay", OTRA)
    with pytest.raises(ErrorMesa, match="Escribí tu respuesta"):
        mesa.responder_como_solicitante(t["numero"], "  ", JUAN)
    t = mesa.responder_como_solicitante(t["numero"], "Uruguay", JUAN)
    assert t["estado"] == C.EN_CURSO
    assert mesa.conversacion(t["numero"], JUAN)[-1]["detalle"] == "El solicitante respondió (portal)"


def test_la_conformidad_la_da_el_solicitante_y_no_quien_va_en_copia(mesa):
    t = _pedido(mesa, cc=[PAULA])
    with pytest.raises(ErrorMesa, match="no está esperando"):
        mesa.conformidad_desde_el_portal(t["numero"], JUAN, True)
    mesa.tomar(t["numero"], ANA)
    mesa.resolver(t["numero"], "Te mandé el Excel", ANA)
    with pytest.raises(ErrorMesa, match="no es un pedido tuyo"):
        mesa.conformidad_desde_el_portal(t["numero"], PAULA, True)
    t = mesa.conformidad_desde_el_portal(t["numero"], JUAN, True, 5)
    assert (t["estado"], t["conformidad"], t["csat"]) == (C.CERRADO, C.CONFORME, 5)
    with pytest.raises(ErrorMesa, match="cerrado"):
        mesa.responder_como_solicitante(t["numero"], "una cosa más", JUAN)


def test_cada_tipo_tiene_su_ayuda_en_el_portal():
    assert set(C.AYUDA) == {t.nombre for t in C.TIPOS}
    assert "FreshService" in C.CANALES and "Portal" in C.CANALES
