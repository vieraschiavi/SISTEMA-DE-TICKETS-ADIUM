from datetime import datetime

from tickets_ec import catalogos as C
from tickets_ec import sla as S


def test_horas_habiles_saltean_fin_de_semana(cfg):
    viernes = datetime(2026, 10, 16, 17, 30)
    lunes = datetime(2026, 10, 19, 10, 0)
    assert S.horas_habiles(viernes, lunes, cfg) == 1.5


def test_horas_habiles_saltean_feriados(cfg):
    # 12/10/2026 es feriado en Uruguay: del viernes 9 a las 17 al martes 13 a las 10 hay 2 horas.
    assert S.horas_habiles(datetime(2026, 10, 9, 17), datetime(2026, 10, 13, 10), cfg) == 2


def test_fuera_de_horario_no_suma(cfg):
    assert S.horas_habiles(datetime(2026, 10, 19, 19), datetime(2026, 10, 19, 23), cfg) == 0


def test_sumar_es_la_inversa(cfg):
    inicio = datetime(2026, 10, 16, 16, 0)
    fin = S.sumar_horas_habiles(inicio, 5, cfg)
    assert fin == datetime(2026, 10, 19, 12, 0)
    assert S.horas_habiles(inicio, fin, cfg) == 5


def test_reloj_detenido_en_espera(cfg):
    ev = [{"en": datetime(2026, 10, 19, 10), "estado_hasta": C.NUEVO},
          {"en": datetime(2026, 10, 19, 11), "estado_hasta": C.EN_ESPERA},
          {"en": datetime(2026, 10, 20, 11), "estado_hasta": C.EN_CURSO}]
    fin = datetime(2026, 10, 20, 12)
    assert S.horas_detenidas(ev, fin, cfg) == 9
    assert S.horas_efectivas(datetime(2026, 10, 19, 10), fin, ev, cfg) == 2


def test_matriz_de_sla():
    assert C.sla_horas("Solicitud de permisos", "Alta") == 9
    assert C.sla_horas("Nuevo desarrollo", "Media") == 20 * 9
    assert C.sla_horas("algo raro", "otra") == C.sla_horas("Otro", "Media")


def test_semaforo():
    assert S.semaforo(1, "Solicitud de permisos", "Alta") == "En plazo"
    assert S.semaforo(8, "Solicitud de permisos", "Alta") == "Por vencer"
    assert S.semaforo(10, "Solicitud de permisos", "Alta") == "Vencido"
