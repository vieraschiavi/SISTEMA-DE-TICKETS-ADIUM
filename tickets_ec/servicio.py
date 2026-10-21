"""
La mesa: todo lo que le puede pasar a un ticket, en un solo lugar.

La app, el proceso programado que lee la casilla, la demo y los tests
llaman a `Mesa`; ninguno toca la base directo. Así una regla —qué
transición vale, cuándo se sella la primera respuesta, qué detiene el reloj—
se escribe una vez y vale para todos.

El reloj es inyectable (`reloj=`): la demo simula dieciocho meses de pedidos
pasando por ESTA misma mesa, con el tiempo que ella decide, en vez de
fabricar filas a mano. Si una regla cambia, la demo y el tablero cambian con
ella.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import catalogos as C
from . import clasificador, plantillas
from . import correo as CO
from . import sla as S
from .almacen import Almacen
from .config import Config

SISTEMA = "sistema"


class ErrorMesa(ValueError):
    """Una operación que la mesa no permite, con el motivo en castellano."""


@dataclass
class ResultadoCorreo:
    message_id: str
    resultado: str          # nuevo | respuesta | ignorado: <motivo>
    numero: str | None = None


def voto_por_correo(asunto: str) -> bool | None:
    """«RE: [EC-00042] Conforme» → True; «… No conforme» → False; otra cosa → None."""
    limpio = clasificador.normalizar(re.sub(r"\[[^\]]*\]", " ", CO.asunto_limpio(asunto or "")))
    if re.match(r"\s*no\s+conforme\b", limpio):
        return False
    if re.match(r"\s*(conforme|si,?\s+conforme)\b", limpio):
        return True
    return None


class Mesa:
    def __init__(self, almacen: Almacen, cfg: Config, salida: CO.BuzonSalida | None = None,
                 reloj=datetime.now, guardar_adjuntos: bool = True):
        self.db = almacen
        self.cfg = cfg
        self.salida = salida or CO.BuzonSalida(None)
        self.reloj = reloj
        self.guardar_adjuntos = guardar_adjuntos
        self._directorio = clasificador.leer_directorio(cfg.directorio)

    # ======================================================================
    # Utilidades
    # ======================================================================
    def ahora(self) -> datetime:
        return self.reloj().replace(microsecond=0)

    def _ticket(self, numero: str) -> dict:
        t = self.db.ticket(numero)
        if not t:
            raise ErrorMesa(f"No existe el ticket {numero}.")
        return t

    def _es_equipo(self, mail: str) -> bool:
        p = self.db.persona(mail) if mail and mail != SISTEMA else None
        return bool(p and p["rol"] in ("analista", "coordinador"))

    def _nombre(self, mail: str | None) -> str:
        if not mail:
            return "sin asignar"
        p = self.db.persona(mail)
        return p["nombre"] if p else mail

    def _mandar(self, para: str, partes: tuple[str, str, str], en_respuesta_a: str = "",
                cc: list[str] | None = None, ticket: dict | None = None) -> None:
        asunto, texto, html = partes
        msg = CO.armar(self.cfg.casilla, self.cfg.nombre_casilla, para, asunto, texto, html,
                       en_respuesta_a=en_respuesta_a, cc=cc)
        self.salida.mandar(msg)
        if ticket:
            self.db.agregar_evento(ticket["id"], self.ahora(), SISTEMA, "correo_saliente", publico=True,
                                   detalle=f"A {para}: {asunto}")

    def _sello_primera_respuesta(self, t: dict, actor: str, cambios: dict) -> None:
        if not t["primera_respuesta_en"] and actor != SISTEMA and self._es_equipo(actor):
            cambios["primera_respuesta_en"] = self.ahora()

    # ======================================================================
    # Equipo
    # ======================================================================
    def alta_analista(self, mail: str, nombre: str, coordinador: bool = False, pais: str = "Uruguay (HQ)",
                      equipo: str = C.EXCELENCIA) -> None:
        """Un integrante de uno de los dos equipos resolutores (su área ES su equipo)."""
        if equipo not in C.EQUIPOS:
            raise ErrorMesa(f"«{equipo}» no es un equipo resolutor ({', '.join(C.EQUIPOS)}).")
        self.db.guardar_persona(mail, nombre, equipo, pais, "coordinador" if coordinador else "analista")

    def equipo_de(self, mail: str | None) -> str | None:
        p = self.db.persona(mail) if mail else None
        return p["area"] if p and p["area"] in C.EQUIPOS else None

    def carga(self, equipo: str | None = None) -> dict[str, int]:
        """Tickets pendientes del equipo por analista (para repartir)."""
        marcas = ",".join("?" for _ in C.PENDIENTES_EQUIPO)
        filas = self.db.consulta(f"SELECT analista_mail, COUNT(*) AS n FROM tickets WHERE estado IN ({marcas}) "
                                 "AND analista_mail IS NOT NULL GROUP BY analista_mail", tuple(C.PENDIENTES_EQUIPO))
        carga = {a["mail"]: 0 for a in self.db.analistas()
                 if a["rol"] == "analista" and (equipo is None or a["area"] == equipo)}
        carga.update({f["analista_mail"]: f["n"] for f in filas if f["analista_mail"] in carga})
        return carga

    def sugerir_analista(self, equipo: str | None = None) -> str | None:
        """El analista del equipo con menos pendientes (a igual carga, el primero por mail)."""
        carga = self.carga(equipo)
        return min(sorted(carga), key=lambda m: carga[m]) if carga else None

    # ======================================================================
    # Crear
    # ======================================================================
    def crear(self, asunto: str, descripcion: str, solicitante_mail: str, solicitante_nombre: str = "", *,
              canal: str = "Manual", tipo: str | None = None, subtipo: str | None = None,
              prioridad: str | None = None, area: str | None = None, pais: str | None = None,
              atc: str | None = None, mercado: str | None = None, fuente_datos: str | None = None,
              tablero: str | None = None, unidad_negocio: str | None = None, cc: list[str] | None = None,
              message_id: str | None = None, adjuntos: list[CO.Adjunto] | None = None,
              equipo: str | None = None, acusar: bool = True) -> dict:
        mail = (solicitante_mail or "").strip().lower()
        if "@" not in mail:
            raise ErrorMesa("El solicitante necesita un correo válido.")
        if not (asunto or "").strip():
            raise ErrorMesa("El pedido necesita un asunto.")
        persona = self.db.persona(mail) or self._directorio.get(mail)
        clas = clasificador.clasificar(asunto, descripcion, mail, persona, self.cfg)
        nombre = (solicitante_nombre or (persona or {}).get("nombre") or mail.split("@")[0]).strip()
        area = area or clas.area
        pais = pais or clas.pais
        if tipo in C.POR_TIPO:      # el que eligió el tipo en el formulario manda sobre el clasificador
            subtipo = subtipo if subtipo in C.SUBTIPOS[tipo] else (
                clas.subtipo if clas.tipo == tipo else C.SUBTIPOS[tipo][0])
            prioridad = prioridad if prioridad in C.POR_PRIORIDAD else C.POR_TIPO[tipo].prioridad
        else:
            tipo, subtipo = clas.tipo, clas.subtipo
        prioridad = prioridad if prioridad in C.POR_PRIORIDAD else clas.prioridad
        atc = (atc or clas.atc or "").strip().upper()
        area_t = (C.area_terapeutica(atc) or "Otra") if atc else clas.area_terapeutica
        mercado = mercado or clas.mercado
        if unidad_negocio not in C.UNIDADES_NEGOCIO:
            unidad_negocio = C.unidad_negocio(atc, mercado or "") if atc else clas.unidad_negocio
        fuente_datos = fuente_datos if fuente_datos in C.FUENTES else clas.fuente_datos
        if equipo not in C.EQUIPOS:
            equipo = clas.equipo if clas.tipo == tipo else C.POR_TIPO[tipo].equipo
        ahora = self.ahora()
        with self.db.transaccion():
            self.db.guardar_persona(mail, nombre, area if area != C.AREA_DEFECTO else None,
                                    pais if pais != C.PAIS_DEFECTO else None,
                                    (persona or {}).get("rol") or "solicitante")
            t = self.db.insertar_ticket(
                self.cfg.prefijo, asunto=asunto.strip()[:250], descripcion=(descripcion or "").strip(),
                solicitante_mail=mail, solicitante_nombre=nombre, area=area, pais=pais, tipo=tipo,
                equipo=equipo, subtipo=subtipo, atc=atc, area_terapeutica=area_t, unidad_negocio=unidad_negocio,
                mercado=mercado,
                fuente_datos=fuente_datos, tablero=(tablero or "").strip() or None,
                prioridad=prioridad, canal=canal, estado=C.NUEVO, subestado=C.subestado_defecto(C.NUEVO),
                cc=", ".join(cc or []), clasificacion=clas.motivo, message_id=message_id,
                creado_en=ahora, actualizado_en=ahora)
            self.db.agregar_evento(t["id"], ahora, mail, "estado", estado_hasta=C.NUEVO, publico=True,
                                   detalle=f"Pedido recibido por {canal.lower()}")
            self._adjuntos(t, adjuntos or [])
            if acusar:
                p = C.POR_PRIORIDAD[prioridad]
                plazo = S.sumar_horas_habiles(ahora, C.sla_horas(tipo, prioridad), self.cfg)
                texto_sla = (f"Te respondemos dentro de {p.horas_respuesta:g} horas hábiles; "
                             f"plazo estimado de resolución: {plazo:%d/%m/%Y %H:%M}.")
                self._mandar(mail, plantillas.acuse(t, texto_sla, self.cfg), en_respuesta_a=message_id or "",
                             ticket=t)
        return self.db.ticket(t["numero"])

    def _adjuntos(self, t: dict, adjuntos: list[CO.Adjunto]) -> None:
        if not adjuntos:
            return
        guardados, omitidos = [], []
        carpeta = Path(self.cfg.carpeta_adjuntos) / t["numero"]
        for a in adjuntos:
            if not self.guardar_adjuntos or len(a.datos) > CO.MAX_ADJUNTO:
                omitidos.append(a.nombre)
                continue
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / a.nombre).write_bytes(a.datos)
            guardados.append(a.nombre)
        detalle = ", ".join(guardados) or "ninguno"
        if omitidos:
            detalle += f" · sin guardar (más de 15 MB o guardado apagado): {', '.join(omitidos)}"
        self.db.agregar_evento(t["id"], self.ahora(), SISTEMA, "adjuntos", detalle=detalle)

    # ======================================================================
    # Moverlo
    # ======================================================================
    def _cambiar(self, t: dict, hacia: str, actor: str, nota: str = "", *, sistema: bool = False,
                 subestado: str | None = None, extra: dict | None = None) -> dict:
        desde = t["estado"]
        if desde == hacia:
            raise ErrorMesa(f"{t['numero']} ya está en «{hacia}».")
        if not C.puede(desde, hacia, sistema=sistema):
            permitidas = ", ".join(sorted(C.TRANSICIONES.get(desde, ()))) or "ninguna (lo decide el solicitante)"
            raise ErrorMesa(f"{t['numero']}: de «{desde}» no se pasa a «{hacia}». Desde ahí: {permitidas}.")
        ahora = self.ahora()
        if subestado and subestado not in C.SUBESTADOS.get(hacia, ()):
            raise ErrorMesa(f"«{subestado}» no es un subestado de «{hacia}».")
        cambios = {"estado": hacia, "subestado": subestado or C.subestado_defecto(hacia), "actualizado_en": ahora}
        if hacia == C.EN_CURSO and not t["en_curso_en"]:
            cambios["en_curso_en"] = ahora
        if hacia == C.EN_ESPERA:
            cambios["veces_en_espera"] = t["veces_en_espera"] + 1
        if hacia == C.RESUELTO:
            cambios["resuelto_en"] = ahora
        if hacia == C.CERRADO:
            cambios["cerrado_en"] = ahora
        if hacia == C.CANCELADO:
            cambios["cancelado_en"] = ahora
        if hacia == C.REABIERTO:
            cambios["reaperturas"] = t["reaperturas"] + 1
        if hacia in (C.EN_CURSO, C.EN_ESPERA, C.RESUELTO):
            self._sello_primera_respuesta(t, actor, cambios)
        cambios.update(extra or {})
        with self.db.transaccion():
            self.db.actualizar_ticket(t["id"], **cambios)
            self.db.agregar_evento(t["id"], ahora, actor, "estado", estado_desde=desde, estado_hasta=hacia,
                                   publico=True, detalle=nota)
        return self.db.ticket(t["numero"])

    def asignar(self, numero: str, analista_mail: str, actor: str, avisar: bool = True) -> dict:
        t = self._ticket(numero)
        if t["estado"] in C.FINALES:
            raise ErrorMesa(f"{numero} está {t['estado'].lower()}: no se reasigna.")
        analista = self.db.persona(analista_mail)
        if not analista or analista["rol"] not in ("analista", "coordinador"):
            raise ErrorMesa(f"{analista_mail} no es del equipo.")
        ahora = self.ahora()
        with self.db.transaccion():
            cambios = {"analista_mail": analista["mail"], "actualizado_en": ahora}
            if not t["asignado_en"]:
                cambios["asignado_en"] = ahora
            equipo = self.equipo_de(analista["mail"])
            if equipo and equipo != t["equipo"]:      # asignarlo a alguien del otro equipo es derivarlo
                cambios["equipo"] = equipo
                self.db.agregar_evento(t["id"], ahora, actor, "derivacion", detalle=f"{t['equipo']} → {equipo}")
            self.db.actualizar_ticket(t["id"], **cambios)
            self.db.agregar_evento(t["id"], ahora, actor, "asignacion",
                                   detalle=f"{self._nombre(t['analista_mail'])} → {analista['nombre']}")
            if t["estado"] == C.NUEVO:
                self._cambiar(self.db.ticket(numero), C.ASIGNADO, actor, f"Asignado a {analista['nombre']}")
            t = self.db.ticket(numero)
            if avisar and analista["mail"] != actor:
                self._mandar(analista["mail"], plantillas.asignado(t, analista["nombre"], self.cfg), ticket=t)
        return self.db.ticket(numero)

    def tomar(self, numero: str, actor: str) -> dict:
        """El analista lo toma y lo empieza."""
        t = self._ticket(numero)
        if t["analista_mail"] != actor:
            t = self.asignar(numero, actor, actor, avisar=False)
        return self._cambiar(t, C.EN_CURSO, actor, "Empezó el trabajo")

    def cambiar_estado(self, numero: str, hacia: str, actor: str, nota: str = "",
                       subestado: str | None = None) -> dict:
        if hacia == C.RESUELTO:
            return self.resolver(numero, nota, actor)
        if hacia == C.EN_ESPERA:
            return self.pedir_informacion(numero, nota, actor, subestado=subestado)
        if hacia == C.CANCELADO:
            return self.cancelar(numero, nota, actor, subestado=subestado)
        return self._cambiar(self._ticket(numero), hacia, actor, nota, subestado=subestado)

    def cambiar_subestado(self, numero: str, subestado: str, actor: str) -> dict:
        t = self._ticket(numero)
        if subestado not in C.SUBESTADOS.get(t["estado"], ()):
            raise ErrorMesa(f"«{subestado}» no es un subestado de «{t['estado']}».")
        with self.db.transaccion():
            self.db.actualizar_ticket(t["id"], subestado=subestado, actualizado_en=self.ahora())
            self.db.agregar_evento(t["id"], self.ahora(), actor, "subestado",
                                   detalle=f"{t['subestado']} → {subestado}")
        return self.db.ticket(numero)

    def reclasificar(self, numero: str, actor: str, *, tipo: str | None = None, subtipo: str | None = None,
                     prioridad: str | None = None, area: str | None = None, pais: str | None = None,
                     atc: str | None = None, area_terapeutica: str | None = None, mercado: str | None = None,
                     fuente_datos: str | None = None, tablero: str | None = None,
                     unidad_negocio: str | None = None) -> dict:
        t = self._ticket(numero)
        cambios = {}
        tipo_final = tipo or t["tipo"]
        if tipo and tipo != t["tipo"] and not subtipo:
            subtipo = C.SUBTIPOS.get(tipo, ("",))[0]
        if atc is not None and atc.strip().upper() != (t["atc"] or "") and not area_terapeutica:
            area_terapeutica = C.area_terapeutica(atc) or ("Otra" if atc.strip() else C.AREA_TERAPEUTICA_DEFECTO)
            if not unidad_negocio:
                unidad_negocio = (C.unidad_negocio(atc, mercado or t["mercado"] or "") if atc.strip()
                                  else C.UNIDAD_NEGOCIO_DEFECTO)
        for campo, valor, validos in (
                ("tipo", tipo, C.POR_TIPO), ("subtipo", subtipo, C.SUBTIPOS.get(tipo_final, ())),
                ("prioridad", prioridad, C.POR_PRIORIDAD), ("area", area, C.AREAS), ("pais", pais, C.PAISES),
                ("area_terapeutica", area_terapeutica, C.AREAS_TERAPEUTICAS), ("fuente_datos", fuente_datos, C.FUENTES),
                ("unidad_negocio", unidad_negocio, C.UNIDADES_NEGOCIO),
                ("atc", atc.strip().upper() if atc is not None else None, None),
                ("mercado", mercado, None), ("tablero", tablero, None)):
            if valor is not None and valor != (t[campo] or "") and (valor or t[campo]):
                if validos is not None and valor not in validos:
                    raise ErrorMesa(f"«{valor}» no es un valor de {campo}.")
                cambios[campo] = valor
        if not cambios:
            return t
        with self.db.transaccion():
            self.db.actualizar_ticket(t["id"], actualizado_en=self.ahora(), **cambios)
            self.db.agregar_evento(t["id"], self.ahora(), actor, "clasificacion",
                                   detalle="; ".join(f"{k}: {t[k]} → {v}" for k, v in cambios.items()))
            if "area" in cambios or "pais" in cambios:   # que el próximo pedido ya venga bien
                self.db.guardar_persona(t["solicitante_mail"], t["solicitante_nombre"],
                                        cambios.get("area"), cambios.get("pais"),
                                        (self.db.persona(t["solicitante_mail"]) or {}).get("rol") or "solicitante")
        return self.db.ticket(numero)

    def derivar(self, numero: str, equipo: str, actor: str, motivo: str = "") -> dict:
        """Pasarlo al otro equipo. Queda sin analista: lo toma alguien de allá."""
        t = self._ticket(numero)
        if equipo not in C.EQUIPOS:
            raise ErrorMesa(f"«{equipo}» no es un equipo resolutor.")
        if equipo == t["equipo"]:
            return t
        if t["estado"] in C.FINALES:
            raise ErrorMesa(f"{numero} está {t['estado'].lower()}: no se deriva.")
        with self.db.transaccion():
            self.db.actualizar_ticket(t["id"], equipo=equipo, analista_mail=None, actualizado_en=self.ahora())
            self.db.agregar_evento(t["id"], self.ahora(), actor, "derivacion",
                                   detalle=f"{t['equipo']} → {equipo}" + (f": {motivo}" if motivo else ""))
        return self.db.ticket(numero)

    def comentar(self, numero: str, texto: str, actor: str, publico: bool = False) -> dict:
        """Una nota interna o, con `publico`, una respuesta al solicitante por correo."""
        t = self._ticket(numero)
        if not (texto or "").strip():
            raise ErrorMesa("El comentario está vacío.")
        with self.db.transaccion():
            cambios = {"actualizado_en": self.ahora()}
            if publico:
                self._sello_primera_respuesta(t, actor, cambios)
            self.db.actualizar_ticket(t["id"], **cambios)
            self.db.agregar_evento(t["id"], self.ahora(), actor, "comentario", publico=publico, detalle=texto)
            if publico:
                cuerpo = CO.escapar(texto).replace("\n", "<br>")
                self._mandar(t["solicitante_mail"], (plantillas.asunto(t), texto, f"<p>{cuerpo}</p>"),
                             en_respuesta_a=t["message_id"] or "", ticket=t)
        return self.db.ticket(numero)

    def pedir_informacion(self, numero: str, pregunta: str, actor: str, subestado: str | None = None) -> dict:
        if not (pregunta or "").strip():
            raise ErrorMesa("¿Qué dato le falta al pedido? La pregunta es lo que recibe el solicitante.")
        t = self._cambiar(self._ticket(numero), C.EN_ESPERA, actor, pregunta, subestado=subestado)
        self._mandar(t["solicitante_mail"],
                     plantillas.pedido_de_informacion(t, pregunta, self._nombre(t["analista_mail"]), self.cfg),
                     en_respuesta_a=t["message_id"] or "", ticket=t)
        return t

    def cancelar(self, numero: str, motivo: str, actor: str, subestado: str | None = None) -> dict:
        if not (motivo or "").strip():
            raise ErrorMesa("Cancelar pide un motivo: queda en el historial y lo lee el solicitante.")
        return self._cambiar(self._ticket(numero), C.CANCELADO, actor, motivo, subestado=subestado)

    # ======================================================================
    # Resolver y conformidad
    # ======================================================================
    def _hash(self, token: str) -> str:
        return hashlib.sha256(f"{self.cfg.secreto}:{token}".encode()).hexdigest()

    def resolver(self, numero: str, resolucion: str, actor: str) -> dict:
        if not (resolucion or "").strip():
            raise ErrorMesa("Contá qué se hizo: es lo que lee el solicitante antes de dar su conformidad.")
        t = self._ticket(numero)
        if not t["analista_mail"]:
            t = self.asignar(numero, actor, actor, avisar=False) if self._es_equipo(actor) else t
        t = self._cambiar(t, C.RESUELTO, actor, resolucion,
                          extra={"resolucion": resolucion, "conformidad": C.PENDIENTE, "csat": None})
        token = secrets.token_urlsafe(24)
        ronda = 1 + len(self.db.consulta("SELECT id FROM encuestas WHERE ticket_id = ?", (t["id"],)))
        self.db.agregar_encuesta(t["id"], ronda, self._hash(token), self.ahora())
        si, no = self._links_encuesta(t, token)
        self._mandar(t["solicitante_mail"],
                     plantillas.resuelto(t, resolucion, si, no, self.cfg.dias_conformidad_tacita, self.cfg),
                     en_respuesta_a=t["message_id"] or "", ticket=t)
        t["_token"] = token        # sólo para quien llamó (la demo, un test): no se guarda
        return t

    def _links_encuesta(self, t: dict, token: str) -> tuple[str, str]:
        """Los dos botones del correo de resuelto. En modo compartido la app
        vive en la PC de cada analista y el solicitante no la alcanza: los
        botones arman un correo a la casilla («[EC-00042] Conforme») y lo
        responde la casilla (ver `procesar_correo`)."""
        if self.cfg.compartida:
            def correo(asunto: str) -> str:
                return f"mailto:{self.cfg.casilla}?subject=" + urllib.parse.quote(f"[{t['numero']}] {asunto}")
            return correo("Conforme"), correo("No conforme")
        base = f"{self.cfg.url_app}/?encuesta={token}"
        return f"{base}&r=si", f"{base}&r=no"

    def encuesta(self, token: str) -> tuple[dict, dict]:
        """(encuesta, ticket) de un link, o ErrorMesa si no vale."""
        e = self.db.encuesta_por_hash(self._hash(token or ""))
        if not e:
            raise ErrorMesa("El link de la encuesta no es válido.")
        t = self.db.consulta("SELECT * FROM tickets WHERE id = ?", (e["ticket_id"],))[0]
        return e, t

    def responder_encuesta(self, token: str, conforme: bool, csat: int | None = None, comentario: str = "") -> dict:
        e, t = self.encuesta(token)
        return self._responder(e, t, conforme, csat, comentario)

    def _responder(self, e: dict, t: dict, conforme: bool, csat: int | None, comentario: str) -> dict:
        if e["resultado"] != C.PENDIENTE:
            raise ErrorMesa(f"Esta encuesta ya se respondió ({e['resultado']}). ¡Gracias!")
        if t["estado"] != C.RESUELTO:
            raise ErrorMesa(f"{t['numero']} ya no está esperando conformidad (está {t['estado'].lower()}).")
        if csat is not None and not (1 <= int(csat) <= 5):
            raise ErrorMesa("La satisfacción va de 1 a 5.")
        if not conforme and not (comentario or "").strip():
            raise ErrorMesa("Contanos qué faltó: es lo que lee el analista para retomarlo.")
        resultado = C.CONFORME if conforme else C.NO_CONFORME
        actor = t["solicitante_mail"]
        with self.db.transaccion():
            self.db.responder_encuesta(e["id"], self.ahora(), resultado, csat, comentario)
            self.db.agregar_evento(t["id"], self.ahora(), actor, "encuesta", publico=True,
                                   detalle=f"{resultado}" + (f" · satisfacción {csat}/5" if csat else "")
                                   + (f" · {comentario}" if comentario else ""))
            if conforme:
                t = self._cambiar(t, C.CERRADO, actor, "Conforme", sistema=True, subestado="Conforme",
                                  extra={"conformidad": C.CONFORME, "csat": csat})
            else:
                t = self._cambiar(t, C.REABIERTO, actor, comentario, sistema=True,
                                  extra={"conformidad": C.NO_CONFORME, "csat": csat})
                if t["analista_mail"]:
                    self._mandar(t["analista_mail"], plantillas.reabierto(t, comentario, self.cfg), ticket=t)
        return t

    def cierre_tacito(self) -> list[str]:
        """Cierra lo resuelto sin respuesta en `dias_conformidad_tacita` días hábiles."""
        limite = self.cfg.dias_conformidad_tacita * (self.cfg.hora_fin - self.cfg.hora_inicio)
        cerrados = []
        for e in self.db.encuestas_pendientes():
            t = self.db.consulta("SELECT * FROM tickets WHERE id = ?", (e["ticket_id"],))[0]
            if t["estado"] != C.RESUELTO:
                continue
            if S.horas_habiles(e["enviada_en"], self.ahora(), self.cfg) < limite:
                continue
            try:
                with self.db.transaccion():
                    # Primero el ticket: en modo compartido es lo que puede chocar con otra PC.
                    self._cambiar(t, C.CERRADO, SISTEMA,
                                  f"Sin respuesta en {self.cfg.dias_conformidad_tacita} días hábiles",
                                  sistema=True, subestado="Conformidad tácita", extra={"conformidad": C.TACITA})
                    self.db.responder_encuesta(e["id"], self.ahora(), C.TACITA, None, "")
            except ErrorMesa:
                continue        # otra PC lo cerró (o lo movió) primero: la próxima sincronización lo trae
            cerrados.append(t["numero"])
        return cerrados

    # ======================================================================
    # Correo entrante
    # ======================================================================
    def procesar_correo(self, m: CO.Mensaje) -> ResultadoCorreo:
        # Sin fecha, el registro del Message-ID fallaría en silencio (INSERT OR
        # IGNORE también ignora el NOT NULL) y el mismo correo entraría dos veces.
        m.fecha = m.fecha or self.ahora()
        if not self.db.reclamar_correo(m.message_id):
            return ResultadoCorreo(m.message_id, "ignorado: ya procesado")
        try:
            return self._procesar(m)
        except BaseException:
            self.db.soltar_correo(m.message_id)
            raise

    def _procesar(self, m: CO.Mensaje) -> ResultadoCorreo:
        motivo = ""
        if m.remitente == self.cfg.casilla.lower():
            motivo = "lo mandó la propia casilla"
        elif m.automatico:
            motivo = f"respuesta automática ({m.automatico})"
        elif "@" not in m.remitente:
            motivo = "sin remitente"
        if motivo:
            self.db.registrar_correo(m.message_id, None, m.fecha, m.remitente, m.asunto, f"ignorado: {motivo}")
            return ResultadoCorreo(m.message_id, f"ignorado: {motivo}")

        numero = CO.numero_en_asunto(m.asunto, self.cfg.prefijo)
        t = self.db.ticket(numero) if numero else None
        if not t:
            for ref in [m.in_reply_to, *m.referencias]:
                if ref and (t := self.db.ticket_por_message_id(ref)):
                    break
        if t and t["estado"] == C.RESUELTO and m.remitente == t["solicitante_mail"] \
                and (voto := voto_por_correo(m.asunto)) is not None:
            return self._encuesta_por_correo(t, m, voto)
        if t and t["estado"] not in C.FINALES:
            return self._respuesta(t, m)
        asunto = CO.asunto_limpio(m.asunto)
        descripcion = m.cuerpo
        if t:   # respondieron un ticket cerrado: es un pedido nuevo, que dice de dónde viene
            descripcion = f"(Seguimiento de {t['numero']}, que estaba {t['estado'].lower()})\n\n{m.cuerpo}"
        nuevo = self.crear(asunto, descripcion, m.remitente, m.nombre, canal="Correo",
                           cc=[c for c in m.cc if c != self.cfg.casilla.lower()], message_id=m.message_id,
                           adjuntos=m.adjuntos)
        self.db.registrar_correo(m.message_id, nuevo["id"], m.fecha, m.remitente, m.asunto, "nuevo")
        return ResultadoCorreo(m.message_id, "nuevo", nuevo["numero"])

    def _encuesta_por_correo(self, t: dict, m: CO.Mensaje, conforme: bool) -> ResultadoCorreo:
        """El solicitante tocó «Conforme» / «No conforme» en el correo de
        resuelto (o lo escribió en el asunto). La primera línea del cuerpo
        puede traer la satisfacción («5», «4/5», «★★★★»)."""
        pendientes = self.db.consulta("SELECT * FROM encuestas WHERE ticket_id = ? AND resultado = ? "
                                      "ORDER BY ronda DESC LIMIT 1", (t["id"], C.PENDIENTE))
        if not pendientes:
            return self._respuesta(t, m)
        texto = (m.cuerpo or "").strip()
        primera = texto.splitlines()[0] if texto else ""
        estrellas = primera.count("★")
        nota = re.match(r"\s*([1-5])\b", primera)
        csat = int(nota.group(1)) if nota else (estrellas if 1 <= estrellas <= 5 else None)
        comentario = texto if (texto and not nota and not estrellas) else "\n".join(texto.splitlines()[1:]).strip()
        if not conforme and not comentario:
            comentario = "No conforme (respondió por correo sin comentario)"
        self._responder(pendientes[0], t, conforme, csat, comentario)
        self.db.registrar_correo(m.message_id, t["id"], m.fecha, m.remitente, m.asunto, "encuesta")
        return ResultadoCorreo(m.message_id, "encuesta", t["numero"])

    def _respuesta(self, t: dict, m: CO.Mensaje) -> ResultadoCorreo:
        with self.db.transaccion():
            self.db.agregar_evento(t["id"], self.ahora(), m.remitente, "correo_entrante", publico=True,
                                   detalle=m.cuerpo or "(sin texto)")
            self.db.actualizar_ticket(t["id"], actualizado_en=self.ahora())
            self._adjuntos(t, m.adjuntos)
            if t["estado"] == C.EN_ESPERA and not self._es_equipo(m.remitente):
                self._cambiar(t, C.EN_CURSO, m.remitente, "El solicitante respondió", sistema=True)
            self.db.registrar_correo(m.message_id, t["id"], m.fecha, m.remitente, m.asunto, "respuesta")
        return ResultadoCorreo(m.message_id, "respuesta", t["numero"])

    def procesar_bandeja(self, fuente) -> list[ResultadoCorreo]:
        """Lee la fuente, procesa cada correo y lo confirma recién después de
        registrarlo. Un correo que rompe no frena a los demás: queda sin
        confirmar (se vuelve a leer) y su error en el resultado."""
        resultados = []
        for clave, crudo in fuente.leer():
            try:
                r = self.procesar_correo(CO.leer(crudo))
            except Exception as error:      # noqa: BLE001 — un correo no frena la bandeja
                resultados.append(ResultadoCorreo(str(clave), f"error: {error}"))
                continue
            fuente.confirmar(clave)
            resultados.append(r)
        return resultados

    # ======================================================================
    # Lectura
    # ======================================================================
    def estado_sla(self, t: dict, eventos: list[dict] | None = None) -> dict:
        """Horas efectivas, vencimiento y semáforo de UN ticket, a hoy."""
        eventos = eventos if eventos is not None else self.db.eventos(t["id"], "estado")
        ahora = self.ahora()
        fin = t["resuelto_en"] if t["estado"] in (C.RESUELTO, C.CERRADO) else (t["cancelado_en"] or ahora)
        efectivas = S.horas_efectivas(t["creado_en"], fin, eventos, self.cfg)
        ultimo = max((e["en"] for e in eventos if e.get("estado_hasta")), default=t["creado_en"])
        return {
            "horas_efectivas": round(efectivas, 2),
            "sla_horas": C.sla_horas(t["tipo"], t["prioridad"]),
            "vence": S.vencimiento(t["creado_en"], t["tipo"], t["prioridad"], eventos, min(fin, ahora), self.cfg),
            "semaforo": S.semaforo(efectivas, t["tipo"], t["prioridad"]),
            "en_estado_desde": ultimo,
        }
