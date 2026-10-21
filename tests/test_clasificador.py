from tickets_ec import clasificador as K
from tickets_ec import demo
from tickets_ec.config import Config


def _c(asunto, cuerpo="", mail="x@adium.com.uy"):
    return K.clasificar(asunto, cuerpo, mail, None, Config())


def test_tipo_subtipo_y_sobre_que():
    c = _c("Necesito el share de rosuvastatina en Chile", "IQVIA TAM")
    assert (c.tipo, c.subtipo, c.atc, c.area_terapeutica, c.fuente_datos) == (
        "Pedido de información", "Consulta de mercado (IQVIA)", "C10", "Cardiovascular", "IQVIA")
    assert _c("Por favor habilitar mismos accesos que Victoria").tipo == "Solicitud de permisos"
    assert _c("El tablero de stocking no actualiza").subtipo == "Tablero que no actualiza"


def test_mercado_mas_largo_gana():
    assert _c("Share de rosuvastatina + ezetimibe").mercado == "ROSUVASTATINA + EZETIMIBE"


def test_atc_escrito_y_urgencia():
    c = _c("Nuevo tablero de lanzamiento A10", "urgente para el comité")
    assert (c.tipo, c.atc, c.area_terapeutica, c.prioridad) == ("Nuevo desarrollo", "A10", "Metab & Obesidad", "Alta")
    assert _c("Lo necesito para hoy, es crítico").prioridad == "Crítica"


def test_equipo_digital():
    assert _c("Mailing por Veeva").equipo == "Digital"
    assert _c("Agregar filtro al tablero de OLE").equipo == "Excelencia Comercial"


def test_pais_por_dominio_y_area_a_completar():
    c = _c("Algo", mail="ana@adium.com.mx")
    assert (c.pais, c.area) == ("México", "Sin área")


def test_acierta_el_tipo_en_los_asuntos_de_la_demo():
    ok = tot = 0
    for tipo, asuntos in demo.ASUNTOS.items():
        for a in asuntos:
            for m, p, t, k in (("Rosuvastatina", "Chile", "Panel Rx", "share"), ("Pantoprazol", "México", "Cierre PEA", "IE")):
                tot += 1
                ok += _c(a.format(m=m, p=p, t=t, k=k)).tipo == tipo
    assert ok / tot >= 0.95, f"{ok}/{tot}"
