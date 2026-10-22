"""
Tickets · Excelencia Comercial & Digital — la app de la mesa.

    streamlit run app/app.py

Para el EQUIPO (Excelencia Comercial y Digital): bandeja, detalle del ticket
con su panel de datos, alta manual, la casilla, los indicadores y el export a
Power BI. El solicitante no entra acá: escribe a la casilla (o usa el portal
de Power Apps, ver `powerapps/`) y sólo abre la página de la encuesta desde
el link de su correo.

La app no tiene reglas propias: todo lo que cambia un ticket pasa por
`tickets_ec.servicio.Mesa`.

Dos modos (`modo` en `config.equipo.toml`, ver docs/EQUIPO.md):

* **local** — la base es un SQLite en esta PC y el que actúa se elige en la
  barra lateral. Para una persona sola o para recorrer la demo.
* **compartida** — cada integrante la abre en SU PC (sola o dentro de la
  suite) y entra con su cuenta de Microsoft de Adium. Todos trabajan sobre
  las mismas listas de SharePoint, que alimenta la casilla: lo que toma o
  resuelve uno lo ven los demás en la siguiente sincronización.
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tickets_ec import acceso, clasificador, compartida, demo, exportar, guia  # noqa: E402
from tickets_ec import catalogos as C  # noqa: E402
from tickets_ec import correo as CO  # noqa: E402
from tickets_ec import indicadores as I  # noqa: E402
from tickets_ec import marca as M  # noqa: E402
from tickets_ec.almacen import Almacen  # noqa: E402
from tickets_ec.config import cargar  # noqa: E402
from tickets_ec.servicio import ErrorMesa, Mesa  # noqa: E402

st.set_page_config(page_title=M.NOMBRE, page_icon=str(M.SIMBOLO), layout="wide")

#: El color de cada estado en la bandeja (relleno con letra que se lee encima).
CHIP = {C.NUEVO: (M.AZUL, M.BLANCO), C.ASIGNADO: (M.GRIS, M.BLANCO), C.EN_CURSO: (M.AMBAR, M.AZUL),
        C.EN_ESPERA: (M.AMBAR, M.AZUL), C.RESUELTO: (M.VERDE_TEXTO, M.BLANCO), C.REABIERTO: (M.ROJO_TEXTO, M.BLANCO),
        C.CERRADO: (M.BORDE, M.AZUL), C.CANCELADO: (M.BORDE, M.AZUL)}
SEMAFORO = {"En plazo": "🟢", "Por vencer": "🟡", "Vencido": "🔴"}

st.markdown(f"""<style>
[data-testid="stSidebar"] {{ border-right: 3px solid {M.ROJO}; }}
.chip {{ display:inline-block; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600;
        text-transform:uppercase; letter-spacing:.3px; }}
.tarjeta {{ border:1px solid {M.BORDE}; border-radius:10px; padding:14px 16px; background:{M.BLANCO}; }}
.tarjeta .n {{ font-size:28px; font-weight:700; color:{M.AZUL}; }}
.tarjeta .t {{ font-size:13px; color:{M.GRIS}; }}
.aviso {{ background:#FFF4D6; border-left:4px solid {M.AMBAR}; padding:10px 14px; border-radius:6px; color:{M.AZUL}; }}
.linea {{ border-left:2px solid {M.BORDE}; padding:2px 0 10px 14px; margin-left:6px; }}
.linea .q {{ color:{M.GRIS}; font-size:12px; }}
</style>""", unsafe_allow_html=True)


# ==========================================================================
# Estado
# ==========================================================================
@st.cache_resource
def _sesion() -> acceso.Sesion:
    """La sesión de Microsoft de quien usa ESTA PC (modo compartido)."""
    return acceso.Sesion(cargar())


@st.cache_resource
def _mesa(mail: str = "") -> Mesa:
    cfg = cargar()
    if cfg.compartida:
        ses = _sesion()
        enviar = (compartida.enviador_tolerante(CO.FuenteGraph.delegada(cfg.casilla, ses.token).enviar)
                  if cfg.envio_activo else None)
        listas = compartida.ListasGraph(cfg.sharepoint_host, cfg.sharepoint_sitio, ses.token)
        # Una copia por persona: dos cuentas en la misma PC no comparten caché.
        copia = Path(cfg.base).parent / f"compartida-{re.sub(r'[^a-z0-9]+', '_', mail)}.db"
        db = compartida.AlmacenCompartido(copia, listas)
        db.sincronizar(completa=db.ultima_sincronizacion is None)
        return Mesa(db, cfg, CO.BuzonSalida(cfg.carpeta_salida, enviar))
    salida = CO.BuzonSalida(cfg.carpeta_salida, _enviador(cfg) if cfg.envio_activo else None)
    return Mesa(Almacen(cfg.base), cfg, salida)


def _enviador(cfg):
    if cfg.envio == "smtp":
        return CO.enviador_smtp(cfg.smtp_host, cfg.smtp_puerto, cfg.casilla, cfg.smtp_clave)
    return CO.FuenteGraph(cfg.graph_tenant, cfg.graph_cliente, cfg.graph_secreto, cfg.casilla).enviar


def pantalla_ingreso() -> acceso.Identidad:
    """En modo compartido, nadie pasa sin su cuenta de Adium."""
    try:
        ses = _sesion()
    except acceso.ErrorAcceso as err:
        st.error(str(err))
        st.stop()
    if ses.quien:
        return ses.quien
    st.image(str(M.LOGO), width=70)
    st.title(M.NOMBRE)
    st.markdown("Entrá con tu **cuenta de Microsoft de Adium**, la misma del correo y de Teams. Se abre la página "
                "de inicio de sesión de Microsoft en el navegador: **la app no ve tu contraseña**.")
    if st.button("🔑 Ingresar con mi cuenta de Adium", type="primary"):
        try:
            with st.spinner("Esperando el inicio de sesión de Microsoft (en la pestaña que se abrió)…"):
                ses.ingresar()
            st.rerun()
        except acceso.ErrorAcceso as err:
            st.error(str(err))
    st.caption("Los tickets, los estados y quién tiene cada uno viven en las listas de SharePoint de la mesa: "
               "cualquier integrante ve lo mismo desde su PC.")
    st.stop()


_cfg = cargar()
quien = pantalla_ingreso() if _cfg.compartida else None
try:
    mesa = _mesa(quien.mail if quien else "")
except (ErrorMesa, acceso.ErrorAcceso) as _err:
    st.error(f"No se pudo abrir la mesa compartida: {_err}")
    st.stop()
cfg = mesa.cfg


def chip(estado: str) -> str:
    fondo, letra = CHIP.get(estado, (M.BORDE, M.AZUL))
    return f"<span class='chip' style='background:{fondo};color:{letra}'>{estado}</span>"


def hace(momento: datetime | None) -> str:
    if not momento:
        return ""
    d = datetime.now() - momento
    if d < timedelta(hours=1):
        return f"{max(1, d.seconds // 60)} minutos"
    if d < timedelta(days=1):
        return f"{d.seconds // 3600} horas {d.seconds % 3600 // 60} minutos"
    return f"{d.days} días"


def ok(texto: str) -> None:
    st.session_state["_aviso"] = texto


def tarjeta(col, numero, titulo: str) -> None:
    col.markdown(f"<div class='tarjeta'><div class='n'>{numero}</div><div class='t'>{titulo}</div></div>",
                 unsafe_allow_html=True)


# ==========================================================================
# La encuesta: lo único que ve el solicitante
# ==========================================================================
def pagina_encuesta(token: str) -> None:
    st.image(str(M.LOGO), width=60)
    st.title("¿Quedó conforme con la resolución?")
    try:
        e, t = mesa.encuesta(token)
    except ErrorMesa as err:
        st.error(str(err))
        return
    st.markdown(f"**{t['numero']} · {t['asunto']}**")
    if t.get("resolucion"):
        st.info(t["resolucion"])
    if e["resultado"] != C.PENDIENTE:
        st.success(f"Ya respondiste esta encuesta ({e['resultado']}). ¡Gracias!")
        return
    preelegido = st.query_params.get("r", "si")
    with st.form("encuesta"):
        conforme = st.radio("Tu respuesta", ["Sí, conforme", "No, falta algo"],
                            index=0 if preelegido == "si" else 1, horizontal=True)
        csat = st.select_slider("¿Qué tan satisfecho quedaste?", options=[1, 2, 3, 4, 5], value=4,
                                format_func=lambda n: f"{n} " + "★" * n)
        comentario = st.text_area("Comentario (obligatorio si falta algo)")
        if st.form_submit_button("Enviar", type="primary"):
            try:
                mesa.responder_encuesta(token, conforme.startswith("Sí"), csat, comentario)
                st.success("¡Gracias! Tu respuesta quedó registrada." if conforme.startswith("Sí")
                           else "Gracias: el pedido volvió a la cola del analista.")
            except ErrorMesa as err:
                st.error(str(err))


if st.query_params.get("encuesta") and not cfg.compartida:
    pagina_encuesta(st.query_params["encuesta"])
    st.stop()


# ==========================================================================
# Barra lateral
# ==========================================================================
with st.sidebar:
    st.image(str(M.LOGO), width=70)
    st.markdown(f"### {M.NOMBRE}")
    st.caption(M.LEMA)
    paginas = ["🏠 Inicio", "📥 Bandeja", "🎫 Ticket", "➕ Nuevo pedido", "📨 Casilla", "📊 Indicadores",
               "📤 Power BI", "🧭 Guía Power Platform", "⚙️ Configuración"]
    if "pagina" not in st.session_state:
        st.session_state["pagina"] = "🎫 Ticket" if st.query_params.get("ticket") else paginas[0]
    pagina = st.radio("Ir a", paginas, key="pagina", label_visibility="collapsed")
    if cfg.compartida:
        actor = quien.mail
        mi_rol = acceso.rol(mesa.db, actor)
        st.markdown(f"👤 **{quien.nombre}** · {mi_rol or 'sin rol en la mesa'}")
        forzar = st.button("🔄 Sincronizar", width="stretch")
    else:
        equipo = mesa.db.analistas()
        # Una PC sola: el que actúa se elige acá y puede todo.
        mi_rol = acceso.COORDINADOR
        if equipo:
            opciones = {f"{a['nombre']} · {a['area']}": a["mail"] for a in equipo}
            actor = opciones[st.selectbox("Actuás como", list(opciones))]
        else:
            actor = ""
            st.warning("Todavía no hay equipo: dalo de alta en ⚙️ Configuración o cargá la demo.")
    st.caption(f"Casilla: {cfg.casilla}")
    st.caption("✉️ Envío de correos: " + ("**activo**" if cfg.envio_activo else
                                          f"apagado — se guardan en `{Path(cfg.carpeta_salida).name}/`"))



def sincronizar(forzar: bool = False) -> str:
    """Trae lo que hicieron los demás y lee la casilla, cada `segundos_sync`
    (o ya, si una escritura chocó con la de otro). Devuelve el error, si lo
    hubo: la app sigue con lo que tiene."""
    db = mesa.db
    ultima = db.ultima_sincronizacion
    # 0.8: el fragmento que llama cada `segundos_sync` no se saltea una vuelta por milisegundos.
    if not (forzar or db.desactualizado or not ultima
            or (datetime.now(UTC) - ultima).total_seconds() >= cfg.segundos_sync * 0.8):
        return ""
    try:
        db.sincronizar()
        if cfg.casilla_automatica:
            res = mesa.procesar_bandeja(CO.FuenteGraph.delegada(cfg.casilla, _sesion().token))
            mesa.cierre_tacito()
            nuevos = [r.numero for r in res if r.resultado == "nuevo"]
            if nuevos:
                st.toast(f"Entraron {len(nuevos)} pedidos por la casilla: {', '.join(nuevos[:5])}")
    except (ErrorMesa, acceso.ErrorAcceso, ValueError) as err:
        return f"No se pudo sincronizar: {err}"
    return ""


def _huella() -> tuple:
    """Cambia si entró o se movió algo: decide si hace falta redibujar la pantalla."""
    t = mesa.db.consulta("SELECT COUNT(*) AS n, MAX(actualizado_en) AS m FROM tickets")[0]
    return t["n"], t["m"], mesa.db.consulta("SELECT COUNT(*) AS n FROM eventos")[0]["n"]


if cfg.compartida:
    if forzar or mesa.db.desactualizado:
        if error := sincronizar(forzar=True):
            st.sidebar.warning(error)
    with st.sidebar:
        @st.fragment(run_every=timedelta(seconds=cfg.segundos_sync))
        def estado_sincronizacion() -> None:
            """Corre sola cada `segundos_sync`: si entró algo, redibuja la app entera."""
            antes = _huella()
            error = sincronizar()
            if _huella() != antes:
                st.rerun()
            cuando = mesa.db.ultima_sincronizacion
            st.caption(f"Sincronizado {cuando.astimezone():%H:%M:%S}" if cuando else "Sin sincronizar")
            if error:
                st.warning(error)
            if mesa.db.pendientes:
                st.caption(f"⏳ {mesa.db.pendientes} cambios esperando red para subir"
                           + (f" ({mesa.db.error_subida})" if mesa.db.error_subida else ""))
            errores = getattr(mesa.salida.enviar, "errores", [])
            if errores:
                st.caption(f"✉️ {len(errores)} correos no salieron (quedaron en la carpeta de salida): {errores[-1]}")

        estado_sincronizacion()
        if st.button("Salir", width="stretch"):
            _sesion().salir()
            st.cache_resource.clear()
            st.rerun()
    if not mi_rol:
        st.error(f"Tu cuenta ({actor}) no está en la lista **Personas** de la mesa como analista o coordinador. "
                 "Pedile a un coordinador que te dé de alta (⚙️ Configuración). Si tenés un pedido para el equipo, "
                 f"escribilo a {cfg.casilla}.")
        st.stop()

if st.session_state.get("_aviso"):
    st.success(st.session_state.pop("_aviso"))


def _tickets_df() -> pd.DataFrame:
    filas = mesa.db.tickets()
    if not filas:
        return pd.DataFrame()
    nombres = {a["mail"]: a["nombre"] for a in mesa.db.analistas(solo_activos=False)}
    estados = {}
    for e in mesa.db.eventos(tipo="estado"):
        estados.setdefault(e["ticket_id"], []).append(e)
    datos = []
    for t in filas:
        s = mesa.estado_sla(t, estados.get(t["id"], []))
        datos.append({
            "Número": t["numero"], "Asunto": t["asunto"], "Solicitante": t["solicitante_nombre"],
            "Área": t["area"], "País": t["pais"], "Equipo": t["equipo"], "Tipo": t["tipo"], "Subtipo": t["subtipo"],
            "ATC": t["atc"] or "", "Área terapéutica": t["area_terapeutica"],
            "Unidad de negocio": t["unidad_negocio"], "Prioridad": t["prioridad"],
            "Estado": t["estado"], "Subestado": t["subestado"],
            "Analista": nombres.get(t["analista_mail"], "Sin asignar"), "Creado": t["creado_en"],
            "SLA": (SEMAFORO.get(s["semaforo"], "") + " " + s["semaforo"]) if t["estado"] in C.PENDIENTES_EQUIPO
            else "", "Vence": s["vence"] if t["estado"] in C.PENDIENTES_EQUIPO else None,
            "_analista": t["analista_mail"]})
    return pd.DataFrame(datos)


def abrir(numero: str) -> None:
    st.session_state["ticket"] = numero
    st.session_state["pagina"] = "🎫 Ticket"


# ==========================================================================
# Inicio
# ==========================================================================
def inicio() -> None:
    st.title(M.NOMBRE)
    df = _tickets_df()
    if df.empty:
        st.info("La mesa está vacía. Cargá la demo para recorrerla, o procesá la casilla en 📨 Casilla.")
        if not cfg.compartida and st.button("Cargar la demo (18 meses simulados, ~30 s)", type="primary"):
            with st.spinner("Simulando dieciocho meses de pedidos…"):
                demo.generar(cfg.base)
            st.cache_resource.clear()
            st.rerun()
        return
    pend = df[df["Estado"].isin(C.PENDIENTES_EQUIPO)]
    c = st.columns(4)
    tarjeta(c[0], len(pend), "Pendientes del equipo")
    tarjeta(c[1], int(pend["SLA"].str.contains("Vencido").sum()), "Vencidos")
    tarjeta(c[2], int((df["Estado"] == C.RESUELTO).sum()), "Esperando conformidad")
    tarjeta(c[3], int((df["Estado"] == C.EN_ESPERA).sum()), "Esperando al solicitante")
    st.subheader("Mis tickets")
    mios = df[(df["_analista"] == actor) & ~df["Estado"].isin(C.FINALES)].sort_values("Creado")
    if mios.empty:
        st.caption("No tenés tickets abiertos.")
    for _, t in mios.head(15).iterrows():
        a, b = st.columns([6, 2])
        a.markdown(f"**{t['Asunto']}** `{t['Número']}`  \n<span style='color:{M.GRIS}'>Creado el "
                   f"{t['Creado']:%d/%m %H:%M} · {t['Solicitante']} · {t['Área']} · {t['Tipo']}</span>",
                   unsafe_allow_html=True)
        b.markdown(chip(t["Estado"]) + f"<br><small>{t['SLA']}</small>", unsafe_allow_html=True)
        if b.button("Abrir", key=f"ab_{t['Número']}"):
            abrir(t["Número"])
            st.rerun()
    sin = df[(df["Estado"] == C.NUEVO)]
    if len(sin):
        st.subheader(f"Sin asignar ({len(sin)})")
        st.dataframe(sin[["Número", "Asunto", "Solicitante", "Área", "Equipo", "Tipo", "Prioridad", "Creado"]],
                     hide_index=True, width="stretch")


# ==========================================================================
# Bandeja
# ==========================================================================
def bandeja() -> None:
    st.title("📥 Bandeja")
    df = _tickets_df()
    if df.empty:
        st.info("No hay tickets todavía.")
        return
    f1, f2, f3, f4 = st.columns(4)
    equipos = f1.multiselect("Equipo resolutor", C.EQUIPOS, default=list(C.EQUIPOS))
    estados = f2.multiselect("Estado", C.ESTADOS, default=[e for e in C.ESTADOS if e not in C.FINALES])
    tipos = f3.multiselect("Tipo de ticket", [t.nombre for t in C.TIPOS])
    areas = f4.multiselect("Área solicitante", C.AREAS)
    g1, g2, g3, g4 = st.columns(4)
    analistas = g1.multiselect("Analista", sorted(df["Analista"].unique()))
    prioridades = g2.multiselect("Prioridad", [p.nombre for p in C.PRIORIDADES])
    terapeuticas = g3.multiselect("Área terapéutica", C.AREAS_TERAPEUTICAS)
    unidades = g4.multiselect("Unidad de negocio", C.UNIDADES_NEGOCIO)
    buscar = st.text_input("Buscar (número, asunto, solicitante, ATC, mercado)")
    v = df[df["Equipo"].isin(equipos) & df["Estado"].isin(estados)]
    for col, sel in (("Tipo", tipos), ("Área", areas), ("Analista", analistas), ("Prioridad", prioridades),
                     ("Área terapéutica", terapeuticas), ("Unidad de negocio", unidades)):
        if sel:
            v = v[v[col].isin(sel)]
    if buscar:
        q = buscar.lower()
        v = v[v.apply(lambda r: q in " ".join(str(x) for x in r.values).lower(), axis=1)]
    v = v.sort_values(["Creado"], ascending=False)
    st.caption(f"{len(v)} tickets · seleccioná una fila para abrirlo")
    sel = st.dataframe(v.drop(columns=["_analista"]), hide_index=True, width="stretch", on_select="rerun",
                       selection_mode="single-row", key="tabla_bandeja",
                       column_config={"Creado": st.column_config.DatetimeColumn(format="DD/MM/YY HH:mm"),
                                      "Vence": st.column_config.DatetimeColumn(format="DD/MM/YY HH:mm")})
    filas = sel.selection.rows if sel and sel.selection else []
    if filas:
        abrir(v.iloc[filas[0]]["Número"])
        st.rerun()
    st.download_button("Exportar a CSV", v.drop(columns=["_analista"]).to_csv(index=False).encode("utf-8-sig"),
                       "bandeja.csv", "text/csv")


# ==========================================================================
# Ticket
# ==========================================================================
def _sel(col, etiqueta, opciones, actual, key):
    opciones = list(opciones)
    if actual and actual not in opciones:
        opciones = [actual] + opciones
    return col.selectbox(etiqueta, opciones, index=opciones.index(actual) if actual in opciones else 0, key=key)


def ticket() -> None:
    numero = st.session_state.get("ticket") or st.query_params.get("ticket") or ""
    numero = st.text_input("Número de ticket", value=numero, placeholder=f"{cfg.prefijo}-00001").strip().upper()
    t = mesa.db.ticket(numero) if numero else None
    if not t:
        if numero:
            st.warning(f"No existe {numero}.")
        return
    st.session_state["ticket"] = numero
    eventos = mesa.db.eventos(t["id"])
    s = mesa.estado_sla(t, [e for e in eventos if e["tipo"] == "estado"])
    st.markdown(f"<div class='aviso'><b>{t['estado']}</b> · {t['subestado'] or ''} &nbsp; desde hace "
                f"{hace(s['en_estado_desde'])}"
                + (f" &nbsp;·&nbsp; SLA {SEMAFORO.get(s['semaforo'], '')} {s['semaforo']}: "
                   f"{s['horas_efectivas']:.1f} de {s['sla_horas']:.0f} horas hábiles · vence {s['vence']:%d/%m %H:%M}"
                   if t["estado"] in C.PENDIENTES_EQUIPO else "") + "</div>", unsafe_allow_html=True)
    st.markdown(f"## #{t['numero']} &nbsp; {t['asunto']}")
    puedo = acceso.puede_actuar(mi_rol, actor, t)
    asigna = acceso.puede_asignar(mi_rol)
    if not puedo and t["estado"] not in C.FINALES:
        st.info(f"Lo tiene {mesa._nombre(t['analista_mail'])}. Podés dejarle una nota; para tomarlo, pedile a un "
                "coordinador que te lo asigne.")
    izq, der = st.columns([3, 2], gap="large")

    with izq:
        st.markdown(f"**{t['solicitante_nombre']}** &lt;{t['solicitante_mail']}&gt; · {t['area']} · {t['pais']} · "
                    f"por {t['canal'].lower()}, el {t['creado_en']:%d/%m/%Y %H:%M}" +
                    (f"  \nCc: {t['cc']}" if t["cc"] else ""), unsafe_allow_html=True)
        st.text(t["descripcion"] or "(sin descripción)")
        if t["clasificacion"]:
            st.caption(f"🤖 Clasificación automática: {t['clasificacion']}")
        st.markdown("#### Acciones")
        a1, a2, a3, a4 = st.columns(4)
        try:
            if puedo and t["estado"] in (C.NUEVO, C.ASIGNADO, C.REABIERTO) and a1.button("▶️ Tomarlo", width="stretch"):
                mesa.tomar(numero, actor)
                ok(f"{numero} en curso.")
                st.rerun()
            with a2.popover("❓ Pedir información", width="stretch",
                            disabled=not puedo or t["estado"] not in (C.NUEVO, C.ASIGNADO, C.EN_CURSO, C.REABIERTO)):
                pregunta = st.text_area("¿Qué le falta al pedido?", key="preg")
                sub = st.selectbox("Subestado", C.SUBESTADOS[C.EN_ESPERA], key="sub_esp")
                if st.button("Enviar al solicitante", type="primary"):
                    mesa.pedir_informacion(numero, pregunta, actor, subestado=sub)
                    ok("Le escribimos al solicitante: el reloj del SLA queda detenido.")
                    st.rerun()
            with a3.popover("✅ Resolver", width="stretch",
                            disabled=not puedo or t["estado"] in (C.RESUELTO, *C.FINALES)):
                resol = st.text_area("Qué se hizo (lo lee el solicitante)", key="resol")
                if st.button("Resolver y pedir conformidad", type="primary"):
                    mesa.resolver(numero, resol, actor)
                    ok("Resuelto: le llegó la encuesta de conformidad al solicitante.")
                    st.rerun()
            with a4.popover("✖️ Cancelar", width="stretch", disabled=not puedo or t["estado"] in C.FINALES):
                motivo = st.text_area("Motivo", key="motivo")
                sub = st.selectbox("Subestado", C.SUBESTADOS[C.CANCELADO], key="sub_can")
                if st.button("Cancelar el ticket"):
                    mesa.cancelar(numero, motivo, actor, subestado=sub)
                    ok("Cancelado.")
                    st.rerun()
        except ErrorMesa as err:
            st.error(str(err))

        st.markdown("#### Responder / nota")
        with st.form("comentario", clear_on_submit=True):
            texto = st.text_area("Texto", label_visibility="collapsed")
            publico = st.toggle("Mandarlo al solicitante por correo (si no, queda como nota interna)")
            if st.form_submit_button("Agregar"):
                try:
                    mesa.comentar(numero, texto, actor, publico)
                    ok("Respuesta enviada." if publico else "Nota agregada.")
                    st.rerun()
                except ErrorMesa as err:
                    st.error(str(err))

        st.markdown("#### Historial")
        nombres = {p["mail"]: p["nombre"] for p in mesa.db.consulta("SELECT mail, nombre FROM personas")}
        for e in reversed(eventos):
            quien = nombres.get(e["usuario"], e["usuario"])
            if e["tipo"] == "estado":
                que = (f"{e['estado_desde']} → {chip(e['estado_hasta'])}" if e["estado_desde"]
                       else chip(e["estado_hasta"]))
            else:
                que = f"<b>{e['tipo'].replace('_', ' ').capitalize()}</b>" + (" · público" if e["publico"] else "")
            detalle = (e["detalle"] or "").replace("<", "&lt;").replace("\n", "<br>")
            st.markdown(f"<div class='linea'>{que} <span class='q'>· {quien} · {e['en']:%d/%m/%Y %H:%M}</span>"
                        f"<br>{detalle}</div>", unsafe_allow_html=True)

    with der:
        st.markdown("### Datos del ticket")
        equipo_mails = {a["mail"]: f"{a['nombre']} · {a['area']}" for a in mesa.db.analistas()}
        with st.form("datos"):
            c1, c2 = st.columns(2)
            tipo = _sel(c1, "Tipo de ticket", C.POR_TIPO, t["tipo"], "d_tipo")
            subtipo = _sel(c2, "Subtipo", C.SUBTIPOS.get(tipo, ()), t["subtipo"], "d_sub")
            prioridad = _sel(c1, "Prioridad", C.POR_PRIORIDAD, t["prioridad"], "d_pri")
            equipo_r = _sel(c2, "Equipo resolutor", C.EQUIPOS, t["equipo"], "d_eq")
            asignado = c1.selectbox("Asignado a", ["(sin asignar)"] + list(equipo_mails),
                                    index=(list(equipo_mails).index(t["analista_mail"]) + 1)
                                    if t["analista_mail"] in equipo_mails else 0,
                                    format_func=lambda m: equipo_mails.get(m, m), key="d_asig", disabled=not asigna)
            subestado = _sel(c2, "Subestado", C.SUBESTADOS.get(t["estado"], ()), t["subestado"], "d_subest")
            area = _sel(c1, "Área solicitante", C.AREAS, t["area"], "d_area")
            pais = _sel(c2, "País", C.PAISES, t["pais"], "d_pais")
            atc = c1.text_input("ATC", value=t["atc"] or "", key="d_atc")
            mercados = [""] + sorted({m["mercado"] for m in clasificador.mercados()})
            mercado = _sel(c2, "Mercado conformado", mercados, t["mercado"] or "", "d_merc")
            terapeutica = _sel(c1, "Área terapéutica", C.AREAS_TERAPEUTICAS, t["area_terapeutica"], "d_at")
            unidad = _sel(c2, "Unidad de negocio", C.UNIDADES_NEGOCIO, t["unidad_negocio"], "d_un")
            fuente = _sel(c1, "Fuente de datos", C.FUENTES, t["fuente_datos"], "d_fuente")
            tablero = c2.text_input("Tablero / informe", value=t["tablero"] or "", key="d_tab")
            if st.form_submit_button("Actualizar", type="primary", width="stretch", disabled=not puedo):
                try:
                    if equipo_r != t["equipo"]:
                        mesa.derivar(numero, equipo_r, actor)
                    if mercado and mercado != (t["mercado"] or "") and not atc.strip():
                        atc = next((m["atc"] for m in clasificador.mercados() if m["mercado"] == mercado), "")
                    cambia_atc = atc.strip().upper() != (t["atc"] or "")
                    mesa.reclasificar(numero, actor, tipo=tipo, subtipo=subtipo, prioridad=prioridad, area=area,
                                      pais=pais, atc=atc, mercado=mercado, fuente_datos=fuente, tablero=tablero,
                                      # si cambió el ATC, área y UN salen de él (salvo que se elijan a mano)
                                      area_terapeutica=None if cambia_atc and terapeutica == t["area_terapeutica"]
                                      else terapeutica,
                                      unidad_negocio=None if cambia_atc and unidad == t["unidad_negocio"] else unidad)
                    if asignado != "(sin asignar)" and asignado != mesa.db.ticket(numero)["analista_mail"]:
                        mesa.asignar(numero, asignado, actor)
                    if subestado != t["subestado"] and subestado in C.SUBESTADOS.get(t["estado"], ()):
                        mesa.cambiar_subestado(numero, subestado, actor)
                    ok("Ticket actualizado.")
                    st.rerun()
                except ErrorMesa as err:
                    st.error(str(err))
        st.caption("Área terapéutica y unidad de negocio salen del ATC (reglas del manual y de la Planilla "
                   "Maestra); se pueden corregir a mano. Conformidad: "
                   f"**{t['conformidad']}**" + (f" · satisfacción {t['csat']}/5" if t["csat"] else "")
                   + (f" · reaperturas: {t['reaperturas']}" if t["reaperturas"] else ""))
        fechas = [("Creado", t["creado_en"]), ("Asignado", t["asignado_en"]),
                  ("Primera respuesta", t["primera_respuesta_en"]), ("En curso", t["en_curso_en"]),
                  ("Resuelto", t["resuelto_en"]), ("Cerrado", t["cerrado_en"]), ("Cancelado", t["cancelado_en"])]
        st.markdown("##### Fechas de cada estado")
        st.dataframe(pd.DataFrame([{"Hito": h, "Fecha": f} for h, f in fechas if f]), hide_index=True,
                     width="stretch", column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")})


# ==========================================================================
# Nuevo pedido
# ==========================================================================
def nuevo() -> None:
    st.title("➕ Nuevo pedido")
    st.caption("Para los pedidos que llegan por Teams, teléfono o en una reunión. Los del correo entran solos.")
    with st.form("nuevo"):
        c1, c2 = st.columns(2)
        mail = c1.text_input("Correo del solicitante")
        nombre = c2.text_input("Nombre (si no está en el directorio)")
        asunto = st.text_input("Asunto")
        descripcion = st.text_area("Qué necesita")
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo de ticket", ["(detectar automáticamente)"] + [t.nombre for t in C.TIPOS])
        prioridad = c2.selectbox("Prioridad", ["(la del tipo)"] + [p.nombre for p in C.PRIORIDADES])
        canal = c3.selectbox("Canal", [c for c in C.CANALES if c != "Correo"])
        c1, c2, c3 = st.columns(3)
        mercado = c1.selectbox("Mercado conformado", [""] + sorted({m["mercado"] for m in clasificador.mercados()}))
        atc = c2.text_input("ATC (si no hay mercado)")
        tablero = c3.text_input("Tablero / informe")
        unidad = st.selectbox("Unidad de negocio", ["(la del ATC)"] + list(C.UNIDADES_NEGOCIO))
        if st.form_submit_button("Crear ticket", type="primary"):
            try:
                if mercado and not atc:
                    atc = next((m["atc"] for m in clasificador.mercados() if m["mercado"] == mercado), "")
                t = mesa.crear(asunto, descripcion, mail, nombre, canal=canal,
                               tipo=None if tipo.startswith("(") else tipo,
                               prioridad=None if prioridad.startswith("(") else prioridad,
                               atc=atc or None, mercado=mercado or None, tablero=tablero or None,
                               unidad_negocio=None if unidad.startswith("(") else unidad)
                ok(f"Creado {t['numero']} · {t['tipo']} / {t['subtipo']} · {t['equipo']}.")
                abrir(t["numero"])
                st.rerun()
            except ErrorMesa as err:
                st.error(str(err))
    if asunto_previo := st.text_input("Probar el clasificador con un asunto", key="probar"):
        c = clasificador.clasificar(asunto_previo, "", "x@" + cfg.dominios[0], None, cfg)
        st.write(f"**{c.tipo}** / {c.subtipo} · prioridad **{c.prioridad}** · equipo **{c.equipo}** · "
                 f"ATC {c.atc or '—'} · {c.area_terapeutica} · UN {c.unidad_negocio} · {c.fuente_datos}")
        st.caption(c.motivo)


# ==========================================================================
# Casilla
# ==========================================================================
def casilla() -> None:
    st.title("📨 Casilla")
    st.markdown(f"**{cfg.nombre_casilla}** · `{cfg.casilla}` · fuente: "
                + ("**la casilla compartida, con tu cuenta** (cada sincronización la lee sola)" if cfg.compartida
                   else f"**{cfg.fuente}**"))
    st.caption("La casilla la crea IT como buzón compartido de Microsoft 365. Cómo pedirla y cómo conectarla: "
               "`docs/CASILLA.md`.")
    c1, c2 = st.columns(2)
    if c1.button("Procesar la casilla ahora", type="primary"):
        try:
            if cfg.compartida:
                fuente = CO.FuenteGraph.delegada(cfg.casilla, _sesion().token)
            elif cfg.fuente == "graph":
                fuente = CO.FuenteGraph(cfg.graph_tenant, cfg.graph_cliente, cfg.graph_secreto, cfg.casilla)
            elif cfg.fuente == "imap":
                fuente = CO.FuenteIMAP(cfg.imap_host, cfg.imap_usuario, clave=cfg.imap_clave)
            else:
                fuente = CO.FuenteCarpeta(cfg.carpeta_entrada)
            res = mesa.procesar_bandeja(fuente)
            cerrados = mesa.cierre_tacito()
            st.success(f"{len(res)} correos procesados · {len(cerrados)} cierres tácitos.")
            st.dataframe(pd.DataFrame([r.__dict__ for r in res]), hide_index=True, width="stretch")
        except Exception as err:      # noqa: BLE001 — se muestra, no se esconde
            st.error(f"No se pudo leer la casilla: {err}")
    archivo = c2.file_uploader("…o subir un correo (.eml)", type=["eml"])
    if archivo and c2.button("Procesar este correo"):
        r = mesa.procesar_correo(CO.leer(archivo.getvalue()))
        st.success(f"{r.resultado} · {r.numero or ''}")
    st.subheader("Últimos correos recibidos")
    st.dataframe(pd.DataFrame(mesa.db.correos()[:200]), hide_index=True, width="stretch")
    st.subheader("Bandeja de salida")
    salida = sorted(Path(cfg.carpeta_salida).glob("*.eml"), reverse=True)[:30] if Path(cfg.carpeta_salida).exists() else []
    for ruta in salida:
        with st.expander(ruta.name):
            msg = CO.leer(ruta.read_bytes())
            st.markdown(f"**Para:** {', '.join(msg.para)}  \n**Asunto:** {msg.asunto}")
            st.text(msg.cuerpo)


# ==========================================================================
# Indicadores
# ==========================================================================
def _pct(v):
    return "—" if v is None else f"{v:.1%}"


def indicadores() -> None:
    st.title("📊 Indicadores")
    t = exportar.tablas(mesa.db, cfg)
    if not t["Tickets"]:
        st.info("Sin datos todavía.")
        return
    c1, c2, c3, c4 = st.columns(4)
    hoy = date.today()
    desde = c1.date_input("Desde", hoy.replace(day=1) - timedelta(days=365))
    hasta = c2.date_input("Hasta", hoy)
    equipos = c3.multiselect("Equipo resolutor", C.EQUIPOS, default=list(C.EQUIPOS))
    tipos = c4.multiselect("Tipo de ticket", [x.nombre for x in C.TIPOS])
    tk = [x for x in t["Tickets"] if x["Equipo resolutor"] in equipos and (not tipos or x["Tipo de ticket"] in tipos)]
    k = I.kpis(tk, t["Encuestas"], desde, hasta)
    filas = [("Tickets recibidos", k["Tickets recibidos"], None), ("Tickets resueltos", k["Tickets resueltos"], None),
             ("Backlog fin de período", k["Backlog fin de período"], None),
             ("Vencidos sin resolver", k["Vencidos sin resolver"], None),
             ("% en SLA", _pct(k["% en SLA"]), k["% en SLA"]),
             ("% respuesta en SLA", _pct(k["% respuesta en SLA"]), k["% respuesta en SLA"]),
             ("Días de resolución", f"{k['Días de resolución'] or 0:.1f}", None),
             ("% conformidad con tácita", _pct(k["% conformidad con tácita"]), k["% conformidad con tácita"]),
             ("Satisfacción (1 a 5)", f"{k['Satisfacción (1 a 5)'] or 0:.2f}", None),
             ("Tasa de reapertura", _pct(k["Tasa de reapertura"]), None),
             ("% sin idas y vueltas", _pct(k["% sin idas y vueltas"]), None),
             ("Índice de efectividad", _pct(k["Índice de efectividad"]), k["Índice de efectividad"])]
    for i in range(0, len(filas), 4):
        cols = st.columns(4)
        for col, (nombre, valor, sem) in zip(cols, filas[i:i + 4], strict=False):
            marca = {"Verde": "🟢", "Ámbar": "🟡", "Rojo": "🔴"}.get(I.semaforo(sem), "") if sem is not None else ""
            tarjeta(col, f"{valor} {marca}", nombre)
    st.caption("Semáforo del área: ≥ 85 % verde, 70-84 % ámbar, < 70 % rojo. Índice = 40 % SLA + 40 % conformidad "
               "+ 20 % sin reapertura. Las definiciones son las mismas que las del tablero de Power BI.")
    cal = [d for d in t["Calendario"] if desde <= d["Fecha"] <= hasta]
    men = pd.DataFrame(I.mensual(tk, t["Encuestas"], cal))
    if not men.empty:
        st.subheader("Mes a mes")
        st.bar_chart(men.set_index("Período")[["Tickets recibidos", "Tickets resueltos"]], stack=False)
        st.line_chart(men.set_index("Período")[["% en SLA", "% conformidad con tácita", "Índice de efectividad"]])
    en_rango = [x for x in tk if desde <= x["Fecha"] <= hasta]
    for titulo, col in (("Por área solicitante", "Área solicitante"), ("Por tipo de ticket", "Tipo de ticket"),
                        ("Por área terapéutica", "Área terapéutica"), ("Por unidad de negocio", "Unidad de negocio"),
                        ("Por analista", "Analista"),
                        ("Por país", "País")):
        st.subheader(titulo)
        d = pd.DataFrame(I.por(en_rango, t["Encuestas"], col))
        d = d[d["Tickets recibidos"] > 0].sort_values("Tickets recibidos", ascending=False)
        st.dataframe(d[[col, "Tickets recibidos", "Pendientes del equipo", "Días de resolución", "% en SLA",
                        "% conformidad con tácita", "Satisfacción (1 a 5)", "Índice de efectividad"]],
                     hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in
                                    ("% en SLA", "% conformidad con tácita", "Índice de efectividad")})


# ==========================================================================
# Power BI
# ==========================================================================
def powerbi() -> None:
    st.title("📤 Power BI")
    st.markdown("El tablero lee un Excel con cuatro tablas (Tickets, Estados, Encuestas, Calendario). Exportá los "
                "datos de la mesa a una carpeta y abrí la plantilla: Power BI pregunta la carpeta la primera vez.")
    carpeta = RAIZ / "datos" / "powerbi"
    if st.button("Exportar los datos de la mesa", type="primary"):
        t = exportar.tablas(mesa.db, cfg)
        exportar.a_csv(t, carpeta)
        destino = carpeta / "Tickets_Excelencia_Comercial_y_Digital.xlsx"
        with pd.ExcelWriter(destino) as w:
            for nombre, df in exportar.a_dataframes(t).items():
                df.to_excel(w, sheet_name=nombre, index=False)
        st.success(f"Exportado en {carpeta.relative_to(RAIZ)}: el Excel y un CSV por tabla.")
        st.download_button("Descargar el Excel", destino.read_bytes(), destino.name)
    base = RAIZ / "powerbi" / "Tickets_Excelencia_Comercial_y_Digital"
    c1, c2, c3 = st.columns(3)
    if base.with_suffix(".pbit").is_file():
        c1.download_button("⬇️ Plantilla .pbit (8 páginas)", base.with_suffix(".pbit").read_bytes(),
                           base.with_suffix(".pbit").name, width="stretch")
    zipeado = base.with_name(base.name + "_PBIP.zip")
    if zipeado.is_file():
        c2.download_button("⬇️ Proyecto PBIP para Fabric (.zip)", zipeado.read_bytes(), zipeado.name,
                           width="stretch")
    if base.with_suffix(".html").is_file():
        c3.download_button("⬇️ Réplica HTML (sin Power BI)", base.with_suffix(".html").read_bytes(),
                           base.with_suffix(".html").name, width="stretch")
    st.markdown("""
**Para tener el `.pbix` y publicarlo en el servicio corporativo:** abrí el `.pbit` en Power BI Desktop, indicá la
carpeta del Excel cuando la pida (`CarpetaDatos`), dejá que cargue y **Archivo → Guardar como → .pbix**. Después,
**Publicar** al workspace del área. (Un `.pbix` con datos sólo lo escribe Power BI Desktop: el modelo va en un
formato binario de Microsoft que ninguna herramienta externa genera de forma confiable.)

**Para Fabric:** el `.zip` es un proyecto **PBIP** (modelo semántico + reporte) — el formato de la integración con
Git de Fabric. Subí la carpeta a un repo de Azure DevOps o GitHub y conectá el workspace; o publicalo por API con
`python powerbi/publicar_fabric.py --workspace <id>`. Detalle en `docs/POWERBI.md`.
""")
    ver = RAIZ / "powerbi" / "VERIFICACION.md"
    if ver.is_file():
        with st.expander("Verificación del tablero (cada KPI contra la app)"):
            st.markdown(ver.read_text(encoding="utf-8"))


# ==========================================================================
# Configuración
# ==========================================================================
def configuracion() -> None:
    st.title("⚙️ Configuración")
    st.subheader("Equipos resolutores")
    st.dataframe(pd.DataFrame(mesa.db.analistas(solo_activos=False)), hide_index=True, width="stretch")
    if not acceso.puede_configurar(mi_rol):
        st.caption("Las altas y bajas del equipo las hace un coordinador.")
    with st.form("alta"):
        c1, c2, c3, c4 = st.columns(4)
        mail = c1.text_input("Correo")
        nombre = c2.text_input("Nombre")
        equipo_n = c3.selectbox("Equipo", C.EQUIPOS)
        coord = c4.toggle("Coordina")
        if st.form_submit_button("Dar de alta", disabled=not acceso.puede_configurar(mi_rol)):
            try:
                mesa.alta_analista(mail, nombre, coordinador=coord, equipo=equipo_n)
                ok(f"{nombre} sumado a {equipo_n}.")
                st.rerun()
            except ErrorMesa as err:
                st.error(str(err))
    st.subheader("SLA de resolución (días hábiles) por tipo y prioridad")
    st.dataframe(pd.DataFrame([{"Tipo de ticket": t.nombre, "Equipo": t.equipo,
                                **{p.nombre: t.dias[p.orden - 1] for p in C.PRIORIDADES}} for t in C.TIPOS]),
                 hide_index=True, width="stretch")
    st.caption("Primera respuesta: " + " · ".join(f"{p.nombre} {p.horas_respuesta:g} h" for p in C.PRIORIDADES)
               + f" hábiles. Día hábil: {cfg.hora_inicio} a {cfg.hora_fin} h, sin feriados. "
               f"Conformidad tácita a los {cfg.dias_conformidad_tacita} días hábiles.")
    st.subheader("Tipos y subtipos")
    st.dataframe(pd.DataFrame([{"Tipo": t.nombre, "Subtipo": s} for t in C.TIPOS for s in t.subtipos]),
                 hide_index=True, width="stretch")


# ==========================================================================
# Guía Power Platform
# ==========================================================================
PROGRESO = RAIZ / "datos" / "guia_progreso.json"


def _progreso() -> dict:
    import json
    try:
        return json.loads(PROGRESO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_progreso(estado: dict) -> None:
    import json
    PROGRESO.parent.mkdir(parents=True, exist_ok=True)
    PROGRESO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def guia_power_platform() -> None:
    st.title("🧭 Guía Power Platform")
    st.markdown("La mesa en el entorno corporativo: **buzón compartido → Power Automate → listas de SharePoint ← "
                "Power Apps**, y el tablero en Power BI. Usa las licencias de Microsoft 365 que ya tienen: sin "
                "licencias premium ni servidor. Las listas, los catálogos y las fórmulas se generan desde los "
                "mismos catálogos que usa esta app.")
    st.warning("**· REVISAR** — los flujos y las pantallas todavía no se armaron en el tenant de Adium. "
               f"La guía deja de estar en revisión cuando pasa la prueba de punta a punta (paso {len(guia.PASOS)}).")
    hechos = _progreso()
    listos = sum(bool(hechos.get(p.clave)) for p in guia.PASOS)
    st.progress(listos / len(guia.PASOS), text=f"{listos} de {len(guia.PASOS)} pasos hechos")
    faltan = guia.faltantes()
    if faltan:
        st.info("Falta generar: " + ", ".join(f"`{f}`" for f in faltan) + " (ver 📤 Power BI).")

    for i, paso in enumerate(guia.PASOS, start=1):
        marca = "✅" if hechos.get(paso.clave) else "⬜"
        with st.expander(f"{marca} **{i} · {paso.titulo}** — {paso.donde} · {paso.tiempo}", expanded=not listos and i == 1):
            for linea in paso.hacer:
                st.markdown(f"- {linea}")
            st.markdown(f"**Cómo saber que quedó:** {paso.prueba}")
            descargas = [a for a in paso.archivos if guia.archivo(a).is_file()]
            if descargas:
                cols = st.columns(min(4, len(descargas)))
                for j, a in enumerate(descargas):
                    ruta = guia.archivo(a)
                    cols[j % len(cols)].download_button(f"⬇️ {ruta.name}", ruta.read_bytes(), ruta.name,
                                                        key=f"dl_{paso.clave}_{j}", width="stretch")
            for documento, prefijo in paso.secciones:
                encontrada = guia.seccion(documento, prefijo)
                if encontrada:
                    titulo, cuerpo = encontrada
                    with st.popover(f"📄 {titulo}", width="stretch"):
                        st.markdown(cuerpo)
            nuevo = st.checkbox("Hecho", value=bool(hechos.get(paso.clave)), key=f"hecho_{paso.clave}")
            if nuevo != bool(hechos.get(paso.clave)):
                hechos[paso.clave] = nuevo
                _guardar_progreso(hechos)
                st.rerun()

    with st.expander("Por qué SharePoint y no Dataverse · permisos · límites"):
        leeme = (guia.POWERAPPS / "README.md").read_text(encoding="utf-8") if (guia.POWERAPPS / "README.md").is_file() else ""
        for titulo in ("Permisos: lo que cada uno ve", "Límites que hay que conocer", "Una sola definición"):
            bloque = re.search(rf"^## {re.escape(titulo)}\n(.*?)(?=^## |\Z)", leeme, re.MULTILINE | re.DOTALL)
            if bloque:
                st.markdown(f"#### {titulo}\n{bloque.group(1)}")


{"🏠 Inicio": inicio, "📥 Bandeja": bandeja, "🎫 Ticket": ticket, "➕ Nuevo pedido": nuevo, "📨 Casilla": casilla,
 "📊 Indicadores": indicadores, "📤 Power BI": powerbi, "🧭 Guía Power Platform": guia_power_platform,
 "⚙️ Configuración": configuracion}[pagina]()
