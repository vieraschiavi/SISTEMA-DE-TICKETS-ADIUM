"""
El portal del que pide: «Enviar un ticket» y «Mis tickets», como el portal
de FreshService de IT pero para los pedidos a Excelencia Comercial & Digital.

Lo ve cualquier cuenta de Adium que entra a la app (o a la suite) y no es
del equipo; el equipo lo tiene como una página más (🌐 Portal), para pedir
algo o ver cómo lo ve el solicitante. Cada uno ve y toca SÓLO lo suyo: el
filtro está en `Mesa.mis_tickets` / `Mesa.conversacion`, no en la pantalla.

Sin reglas propias: todo pasa por `tickets_ec.servicio.Mesa`.
"""
from __future__ import annotations

import streamlit as st

from tickets_ec import catalogos as C
from tickets_ec import clasificador
from tickets_ec import correo as CO
from tickets_ec import marca as M
from tickets_ec.servicio import ErrorMesa

VISTAS = ("🏠 Inicio", "➕ Enviar un ticket", "🎫 Mis tickets")
SIN_TIPO = "(que lo clasifique el equipo)"

ESTILO = f"""<style>
.portal-barra {{ background:{M.AZUL}; color:{M.BLANCO}; padding:12px 18px; border-radius:8px; display:flex;
                 justify-content:space-between; align-items:center; margin-bottom:14px; }}
.portal-barra b {{ font-size:17px; letter-spacing:.2px; }}
.portal-barra span {{ font-size:13px; opacity:.9; }}
.fila-ticket {{ border:1px solid {M.BORDE}; border-radius:8px; padding:10px 14px; margin-bottom:8px; background:{M.BLANCO}; }}
.fila-ticket .q {{ color:{M.GRIS}; font-size:12px; }}
.espera {{ background:#FFF4D6; border-left:4px solid {M.AMBAR}; padding:6px 10px; border-radius:4px; font-size:13px;
           color:{M.AZUL}; margin-top:6px; }}
.panel {{ border:1px solid {M.BORDE}; border-radius:8px; padding:12px 14px; background:{M.FONDO}; }}
.panel dt {{ color:{M.GRIS}; font-size:12px; margin-top:6px; }}
.panel dd {{ margin:0; color:{M.AZUL}; font-weight:600; }}
</style>"""


def _plazo(t) -> str:
    dias = t.dias[C.POR_PRIORIDAD[t.prioridad].orden - 1]
    return f"{dias} día hábil" if dias == 1 else f"{dias} días hábiles"


def _adjuntos(archivos) -> list[CO.Adjunto]:
    return [CO.Adjunto(f.name, f.type or "application/octet-stream", f.getvalue()) for f in archivos or []]


def _ir(vista: str, numero: str | None = None) -> None:
    st.session_state["portal_vista"] = vista
    if numero:
        st.session_state["portal_ticket"] = numero


def mostrar(mesa, mail: str, nombre: str, chip, hace, mail_editable: bool = False) -> None:
    """El portal entero. `chip` y `hace` son los de la app, para que el estado se vea igual en los dos lados.
    `mail_editable`: en modo local (demo) se elige quién pide; con la cuenta de Adium, no."""
    st.markdown(ESTILO, unsafe_allow_html=True)
    barra = st.container()
    if mail_editable:
        st.session_state.setdefault("portal_mail", mail)
        mail = st.text_input("Pedís como (modo local; en el modo compartido es tu cuenta de Adium)",
                             key="portal_mail").strip().lower()
        p = mesa.db.persona(mail) if mail else None
        nombre = (p or {}).get("nombre") or mail.split("@")[0]
    barra.markdown(f"<div class='portal-barra'><b>🎫 Pedidos a Excelencia Comercial &amp; Digital</b>"
                   f"<span>{CO.escapar(nombre)} · {CO.escapar(mail)}</span></div>", unsafe_allow_html=True)
    if "@" not in (mail or ""):
        st.info("Escribí tu correo de Adium para ver tus pedidos.")
        return
    if st.session_state.get("_aviso_portal"):
        st.success(st.session_state.pop("_aviso_portal"))
    # Lo que pidió la corrida anterior (después de «Enviar»): se aplica ANTES de dibujar los
    # widgets, porque Streamlit no deja cambiar el valor de uno que ya se dibujó.
    if pendiente := st.session_state.pop("_portal_ir", None):
        _ir(*pendiente)
        for k in ("pt_cc", "pt_asunto", "pt_desc", "pt_tablero", "pt_archivos"):
            st.session_state.pop(k, None)
    st.session_state.setdefault("portal_vista", VISTAS[0])
    vista = st.radio("Portal", VISTAS, key="portal_vista", horizontal=True, label_visibility="collapsed")
    if vista == VISTAS[0]:
        _inicio(mesa, mail, nombre)
    elif vista == VISTAS[1]:
        _enviar(mesa, mail, nombre)
    else:
        _mis_tickets(mesa, mail, chip, hace)


# ==========================================================================
# Inicio
# ==========================================================================
def _inicio(mesa, mail: str, nombre: str) -> None:
    mios = mesa.mis_tickets(mail)
    abiertos = [t for t in mios if t["estado"] not in C.FINALES]
    esperando = [t for t in mios if t["estado"] == C.EN_ESPERA and t["solicitante_mail"] == mail]
    conformidad = [t for t in mios if t["estado"] == C.RESUELTO and t["solicitante_mail"] == mail]
    st.markdown(f"### Hola {CO.escapar(nombre.split(' ')[0])}: ¿qué necesitás del área?")
    c = st.columns(3)
    for col, n, texto in ((c[0], len(abiertos), "Pedidos abiertos"), (c[1], len(esperando), "Esperando tu respuesta"),
                          (c[2], len(conformidad), "Para dar tu conformidad")):
        col.markdown(f"<div class='tarjeta'><div class='n'>{n}</div><div class='t'>{texto}</div></div>",
                     unsafe_allow_html=True)
    b1, b2, _ = st.columns([1, 1, 2])
    b1.button("➕ Nuevo ticket", type="primary", width="stretch", on_click=_ir, args=(VISTAS[1],))
    b2.button("🎫 Ver mis tickets", width="stretch", on_click=_ir, args=(VISTAS[2],))
    st.markdown("#### Qué se le puede pedir al área")
    st.dataframe([{"Tipo de pedido": t.nombre, "Por ejemplo": ", ".join(s for s in t.subtipos if s != "Sin detalle"),
                   "Plazo habitual": _plazo(t),
                   "Lo atiende": t.equipo} for t in C.TIPOS], hide_index=True, width="stretch")
    st.caption(f"También podés escribir a {mesa.cfg.casilla}: entra igual, como ticket.")


# ==========================================================================
# Enviar un ticket
# ==========================================================================
def _enviar(mesa, mail: str, nombre: str) -> None:
    st.markdown("### Enviar un ticket")
    izq, der = st.columns([3, 2], gap="large")
    with izq:
        st.text_input("Solicitante", value=mail, disabled=True, key="pt_solicitante")
        cc = st.text_input("Añadir CC (correos separados por coma)", key="pt_cc")
        tipo = st.selectbox("Tipo de pedido", [SIN_TIPO] + [t.nombre for t in C.TIPOS], key="pt_tipo")
        c1, c2 = st.columns(2)
        mercados = [""] + sorted({m["mercado"] for m in clasificador.mercados()})
        mercado = c1.selectbox("Mercado (si aplica)", mercados, key="pt_mercado", format_func=lambda m: m or "—")
        tablero = c2.text_input("Tablero o informe (si aplica)", key="pt_tablero")
        asunto = st.text_input("Asunto *", key="pt_asunto")
        descripcion = st.text_area("Descripción *", height=160, key="pt_desc")
        archivos = st.file_uploader("Adjuntar archivos", accept_multiple_files=True, key="pt_archivos")
        e1, e2, _ = st.columns([1, 1, 3])
        if e1.button("Enviar", type="primary", width="stretch"):
            if not descripcion.strip():
                st.error("Contanos qué necesitás en la descripción.")
                return
            try:
                atc = next((m["atc"] for m in clasificador.mercados() if m["mercado"] == mercado), None) if mercado else None
                t = mesa.crear(asunto, descripcion, mail, nombre, canal="Portal",
                               tipo=None if tipo == SIN_TIPO else tipo, atc=atc, mercado=mercado or None,
                               tablero=tablero or None,
                               cc=[x.strip().lower() for x in cc.split(",") if "@" in x],
                               adjuntos=_adjuntos(archivos))
            except ErrorMesa as err:
                st.error(str(err))
                return
            st.session_state["_aviso_portal"] = (f"Recibimos tu pedido {t['numero']} · {t['tipo']}. Te avisamos por "
                                                 "correo cada vez que cambie.")
            st.session_state["_portal_ir"] = (VISTAS[2], t["numero"])
            st.rerun()
        e2.button("Cancelar", width="stretch", on_click=_ir, args=(VISTAS[0],))
    with der:
        st.markdown("#### Antes de enviar")
        if tipo == SIN_TIPO:
            st.markdown("Si no sabés qué tipo es, dejalo así: el equipo lo clasifica al recibirlo (y lo lee el "
                        "clasificador automático por el asunto y la descripción).")
        else:
            t = C.POR_TIPO[tipo]
            st.markdown(f"**{t.nombre}** · lo atiende **{t.equipo}** · plazo habitual **{_plazo(t)}**")
            st.info(C.AYUDA.get(tipo, C.AYUDA["Otro"]))
        st.caption("Un pedido completo no queda «esperando tu respuesta»: el reloj del plazo corre desde que entra.")


# ==========================================================================
# Mis tickets
# ==========================================================================
def _mis_tickets(mesa, mail: str, chip, hace) -> None:
    mios = mesa.mis_tickets(mail)
    if not mios:
        st.info("Todavía no tenés pedidos. Tocá «➕ Enviar un ticket».")
        return
    elegido = st.session_state.get("portal_ticket")
    if elegido and any(t["numero"] == elegido for t in mios):
        _detalle(mesa, mail, elegido, chip, hace)
        return
    ver = st.radio("Ver", ("Abiertos", "Todos"), horizontal=True, key="portal_filtro")
    filas = [t for t in mios if ver == "Todos" or t["estado"] not in C.FINALES]
    st.caption(f"{len(filas)} pedidos")
    for t in filas:
        a, b = st.columns([6, 1])
        aviso = ""
        if t["estado"] == C.EN_ESPERA:
            aviso = "<div class='espera'>⏳ Esperando tu respuesta</div>"
        elif t["estado"] == C.RESUELTO:
            aviso = "<div class='espera'>✅ Resuelto: contanos si quedó conforme</div>"
        a.markdown(f"<div class='fila-ticket'>{chip(t['estado'])} &nbsp; <b>{CO.escapar(t['asunto'])}</b> "
                   f"<span class='q'>#{t['numero']}</span><br><span class='q'>Creado el {t['creado_en']:%d/%m/%Y %H:%M}"
                   f" · {CO.escapar(t['tipo'])} · {CO.escapar(t['equipo'] or '')}</span>{aviso}</div>",
                   unsafe_allow_html=True)
        b.button("Ver", key=f"pv_{t['numero']}", width="stretch", on_click=_ir, args=(VISTAS[2], t["numero"]))


def _volver() -> None:
    st.session_state.pop("portal_ticket", None)


def _detalle(mesa, mail: str, numero: str, chip, hace) -> None:
    t = mesa.db.ticket(numero)
    st.button("← Mis tickets", on_click=_volver)
    eventos = mesa.conversacion(numero, mail)
    desde = max((e["en"] for e in eventos if e["tipo"] == "estado"), default=t["creado_en"])
    st.markdown(f"## #{t['numero']} &nbsp; {CO.escapar(t['asunto'])}", unsafe_allow_html=True)
    if t["estado"] == C.EN_ESPERA:
        st.markdown(f"<div class='espera'>⏳ Esperando tu respuesta desde hace {hace(desde)}</div>",
                    unsafe_allow_html=True)
    izq, der = st.columns([3, 2], gap="large")
    with izq:
        st.text(t["descripcion"] or "(sin descripción)")
        st.markdown("#### Conversación")
        for e in eventos:
            quien = "Vos" if e["usuario"] == mail else ("Sistema" if e["usuario"] == "sistema"
                                                       else mesa._nombre(e["usuario"]))
            que = chip(e["estado_hasta"]) if e["tipo"] == "estado" else f"<b>{'Encuesta' if e['tipo'] == 'encuesta' else 'Mensaje'}</b>"
            detalle = CO.escapar(e["detalle"] or "").replace("\n", "<br>")
            st.markdown(f"<div class='linea'>{que} <span class='q'>· {CO.escapar(quien)} · {e['en']:%d/%m/%Y %H:%M}"
                        f"</span><br>{detalle}</div>", unsafe_allow_html=True)
        if t["estado"] == C.RESUELTO and t["solicitante_mail"] == mail and mesa._encuesta_pendiente(t):
            _conformidad(mesa, mail, numero)
        elif t["estado"] not in C.FINALES:
            with st.form(f"resp_{numero}", clear_on_submit=True):
                texto = st.text_area("Responder")
                archivos = st.file_uploader("Adjuntar", accept_multiple_files=True)
                if st.form_submit_button("Enviar respuesta", type="primary"):
                    try:
                        mesa.responder_como_solicitante(numero, texto, mail, _adjuntos(archivos))
                        st.session_state["_aviso_portal"] = "Listo: tu respuesta quedó en el ticket."
                        st.rerun()
                    except ErrorMesa as err:
                        st.error(str(err))
    with der:
        s = mesa.estado_sla(t)
        filas = [("Estado", t["estado"]), ("Subestado", t["subestado"] or "—"), ("Tipo de pedido", t["tipo"]),
                 ("Prioridad", t["prioridad"]), ("Equipo", t["equipo"]),
                 ("Asignado a", mesa._nombre(t["analista_mail"]) if t["analista_mail"] else "Sin asignar"),
                 ("Creado", f"{t['creado_en']:%d/%m/%Y %H:%M}")]
        if t["estado"] in C.PENDIENTES_EQUIPO:
            filas.append(("Plazo estimado", f"{s['vence']:%d/%m/%Y %H:%M}"))
        if t["conformidad"] not in (C.SIN_ENCUESTA, C.PENDIENTE):
            filas.append(("Conformidad", t["conformidad"]))
        st.markdown("<div class='panel'><b>Datos del ticket</b><dl>" +
                    "".join(f"<dt>{k}</dt><dd>{CO.escapar(str(v))}</dd>" for k, v in filas) + "</dl></div>",
                    unsafe_allow_html=True)


def _conformidad(mesa, mail: str, numero: str) -> None:
    st.markdown("#### ¿Quedó conforme con la resolución?")
    with st.form(f"conf_{numero}"):
        conforme = st.radio("Tu respuesta", ["Sí, conforme", "No, falta algo"], horizontal=True)
        csat = st.select_slider("¿Qué tan satisfecho quedaste?", options=[1, 2, 3, 4, 5], value=4,
                                format_func=lambda n: f"{n} " + "★" * n)
        comentario = st.text_area("Comentario (obligatorio si falta algo)")
        if st.form_submit_button("Enviar", type="primary"):
            try:
                mesa.conformidad_desde_el_portal(numero, mail, conforme.startswith("Sí"), csat, comentario)
                st.session_state["_aviso_portal"] = ("¡Gracias! Cerramos el pedido." if conforme.startswith("Sí")
                                                     else "Gracias: el pedido volvió al equipo.")
                st.rerun()
            except ErrorMesa as err:
                st.error(str(err))
