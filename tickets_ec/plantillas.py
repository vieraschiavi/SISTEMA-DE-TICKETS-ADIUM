"""
Los correos que manda la mesa, con la marca de Adium.

Todo lo que viene del solicitante (asunto, nombre, texto) pasa por
`escapar()` antes de entrar al HTML: un asunto con `<script>` o con un link
armado no puede convertirse en contenido del correo que manda la casilla
oficial del área.

Cada correo lleva el número en el asunto entre corchetes (`[EC-00042]`):
así la respuesta del solicitante vuelve al mismo ticket aunque su cliente de
correo pierda las cabeceras del hilo.
"""
from __future__ import annotations

from . import marca as M
from .correo import escapar


def _marco(titulo: str, cuerpo_html: str, pie: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;background:{M.FONDO};font-family:Segoe UI,Arial,sans-serif;color:{M.AZUL}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{M.FONDO};padding:24px 0">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:{M.BLANCO};border:1px solid {M.BORDE};border-radius:8px;overflow:hidden">
<tr><td style="background:{M.ROJO_TEXTO};color:{M.BLANCO};padding:14px 24px;font-size:16px;font-weight:600">{escapar(titulo)}</td></tr>
<tr><td style="padding:24px;font-size:14px;line-height:1.55">{cuerpo_html}</td></tr>
<tr><td style="padding:12px 24px;border-top:1px solid {M.BORDE};color:{M.GRIS};font-size:12px">{pie}</td></tr>
</table></td></tr></table></body></html>"""


def _pie(cfg) -> str:
    return (f"{escapar(cfg.nombre_casilla)} · {escapar(cfg.casilla)}<br>"
            "Para sumar información respondé este correo sin cambiar el asunto.")


def _parrafos(texto: str) -> str:
    return "".join(f"<p style='margin:0 0 10px'>{escapar(p)}</p>" for p in (texto or "").split("\n") if p.strip())


def asunto(t: dict, texto: str = "") -> str:
    return f"[{t['numero']}] {texto or t['asunto']}"


def acuse(t: dict, sla_texto: str, cfg) -> tuple[str, str, str]:
    """Recibimos tu pedido."""
    nombre = (t.get("solicitante_nombre") or "").split(" ")[0]
    texto = (f"Hola {nombre}:\n\nRecibimos tu pedido «{t['asunto']}» y le asignamos el número {t['numero']}.\n"
             f"Tipo: {t['tipo']} · Prioridad: {t['prioridad']}.\n{sla_texto}\n\n"
             f"Para sumar información, respondé este correo sin cambiar el asunto.\n\n{cfg.nombre_casilla}")
    html = _marco(f"Recibimos tu pedido · {t['numero']}", (
        f"<p>Hola {escapar(nombre)}:</p>"
        f"<p>Recibimos tu pedido <b>«{escapar(t['asunto'])}»</b> y le asignamos el número "
        f"<b>{escapar(t['numero'])}</b>.</p>"
        f"<p>Tipo: <b>{escapar(t['tipo'])}</b> · Prioridad: <b>{escapar(t['prioridad'])}</b><br>"
        f"{escapar(sla_texto)}</p>"), _pie(cfg))
    return asunto(t), texto, html


def asignado(t: dict, analista_nombre: str, cfg) -> tuple[str, str, str]:
    """Al analista: tenés un ticket."""
    url = f"{cfg.url_app}/?ticket={t['numero']}"
    texto = (f"{analista_nombre}: te asignaron {t['numero']} · {t['asunto']}\n"
             f"Solicitante: {t['solicitante_nombre']} ({t['area']}, {t['pais']})\n"
             f"Prioridad {t['prioridad']} · {t['tipo']}\n{url}")
    html = _marco(f"Te asignaron {t['numero']}", (
        f"<p><b>{escapar(t['asunto'])}</b></p>"
        f"<p>Solicitante: {escapar(t['solicitante_nombre'])} · {escapar(t['area'])} · {escapar(t['pais'])}<br>"
        f"Prioridad <b>{escapar(t['prioridad'])}</b> · {escapar(t['tipo'])}</p>"
        f"{_parrafos(t.get('descripcion') or '')}"
        f"<p><a href='{escapar(url)}' style='color:{M.ROJO_TEXTO}'>Abrir el ticket</a></p>"), _pie(cfg))
    return asunto(t, f"Asignado: {t['asunto']}"), texto, html


def pedido_de_informacion(t: dict, pregunta: str, analista: str, cfg) -> tuple[str, str, str]:
    texto = (f"Hola:\n\nPara avanzar con {t['numero']} necesitamos:\n\n{pregunta}\n\n"
             f"Respondé este correo y el pedido vuelve a la cola de {analista}.\n\n{cfg.nombre_casilla}")
    html = _marco(f"Necesitamos un dato · {t['numero']}", (
        f"<p>Para avanzar con <b>{escapar(t['asunto'])}</b> necesitamos:</p>"
        f"<div style='border-left:3px solid {M.ROJO};padding:4px 12px;margin:12px 0'>{_parrafos(pregunta)}</div>"
        f"<p>Respondé este correo y el pedido vuelve a la cola de {escapar(analista)}.</p>"), _pie(cfg))
    return asunto(t), texto, html


def resuelto(t: dict, resolucion: str, link_si: str, link_no: str, dias: int, cfg) -> tuple[str, str, str]:
    """Resuelto + la encuesta de conformidad, en el mismo correo."""
    texto = (f"Hola:\n\nResolvimos {t['numero']} · {t['asunto']}.\n\n{resolucion}\n\n"
             f"¿Quedó conforme con la resolución?\n  Sí, conforme: {link_si}\n  No, falta algo: {link_no}\n\n"
             f"Si no respondés en {dias} días hábiles, el ticket se cierra como conforme.\n\n{cfg.nombre_casilla}")
    boton = ("display:inline-block;padding:10px 18px;border-radius:6px;text-decoration:none;"
             "font-weight:600;margin-right:8px")
    html = _marco(f"Resolvimos tu pedido · {t['numero']}", (
        f"<p><b>{escapar(t['asunto'])}</b></p>{_parrafos(resolucion)}"
        f"<p style='margin-top:18px'><b>¿Quedó conforme con la resolución?</b></p>"
        f"<p><a href='{escapar(link_si)}' style='{boton};background:{M.VERDE_TEXTO};color:{M.BLANCO}'>Sí, conforme</a>"
        f"<a href='{escapar(link_no)}' style='{boton};background:{M.ROJO_TEXTO};color:{M.BLANCO}'>No, falta algo</a></p>"
        f"<p style='color:{M.GRIS};font-size:12px'>Si no respondés en {dias} días hábiles, el ticket se cierra "
        "como conforme (conformidad tácita).</p>"), _pie(cfg))
    return asunto(t, f"Resuelto: {t['asunto']}"), texto, html


def reabierto(t: dict, comentario: str, cfg) -> tuple[str, str, str]:
    """Al analista: el solicitante no quedó conforme."""
    texto = f"{t['numero']} volvió: el solicitante no quedó conforme.\n\n{comentario}"
    html = _marco(f"No conforme · {t['numero']}", (
        f"<p><b>{escapar(t['asunto'])}</b> volvió a la cola: el solicitante marcó «No conforme».</p>"
        f"{_parrafos(comentario or '(sin comentario)')}"), _pie(cfg))
    return asunto(t, f"Reabierto: {t['asunto']}"), texto, html
