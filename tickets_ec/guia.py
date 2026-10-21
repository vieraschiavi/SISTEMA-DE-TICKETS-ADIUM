"""
La guía para llevar la mesa a Power Platform, como datos.

La lee la página «🧭 Guía Power Platform» de la app, la misma que se abre
dentro de la suite Adium All in One. El texto largo no se copia acá: cada
paso apunta a su sección de `powerapps/FLUJOS.md` o `powerapps/APP.md`, que
siguen siendo la fuente. Así la guía en pantalla y la del repo no pueden
decir cosas distintas.

Sin Streamlit: se prueba sola.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
POWERAPPS = RAIZ / "powerapps"


@dataclass(frozen=True)
class Paso:
    clave: str
    titulo: str
    donde: str
    tiempo: str
    hacer: tuple[str, ...]
    prueba: str
    archivos: tuple[str, ...] = ()
    #: (documento, prefijo del título de las secciones `## ` que se muestran)
    secciones: tuple[tuple[str, str], ...] = field(default_factory=tuple)


PASOS = (
    Paso("it", "Pedirle a IT el buzón, la cuenta de servicio y el sitio", "Correo a IT", "1 pedido",
         ("Buzón compartido tickets.excelenciacomercial@adium.com.uy («Tickets · Excelencia Comercial & Digital»), "
          "con Acceso total y Enviar como para los dos equipos.",
          "Una cuenta de servicio con licencia M365 (svc-tickets-ec): es la dueña de los flujos.",
          "Un sitio de SharePoint «Tickets EC»: edición para Excelencia Comercial, Digital y la cuenta de servicio; "
          "lectura para Adium.",
          "Opcional: una app de Entra ID con Sites.Selected (sólo lectura) para el export diario a Power BI."),
         "IT confirma el buzón y el sitio, y la cuenta de servicio entra a los dos.",
         ("docs/CASILLA.md",)),
    Paso("listas", "Crear las 9 listas de SharePoint", "PowerShell 7 + PnP.PowerShell", "10 min",
         ("Install-Module PnP.PowerShell -Scope CurrentUser",
          "./powerapps/sharepoint/Provisionar-Listas.ps1 -Sitio https://<tenant>.sharepoint.com/sites/TicketsEC "
          "-ClientId <guid>",
          "El script crea las columnas, las opciones, los índices y carga los catálogos (reglas del clasificador, "
          "subtipos, SLA, mercados de HQ, feriados). Es idempotente: se puede volver a correr."),
         "En el sitio aparecen Tickets, Eventos, Encuestas, Personas, ReglasClasificacion, Mercados, Feriados, "
         "Subtipos y SLA, y las cinco de referencia tienen filas.",
         ("powerapps/sharepoint/Provisionar-Listas.ps1", "powerapps/sharepoint/esquema.json",
          "powerapps/sharepoint/reglas_clasificacion.csv", "powerapps/sharepoint/subtipos.csv",
          "powerapps/sharepoint/sla.csv", "powerapps/sharepoint/mercados.csv", "powerapps/sharepoint/feriados.csv")),
    Paso("equipo", "Cargar el equipo en la lista Personas", "SharePoint", "10 min",
         ("Una fila por integrante: Nombre, Mail, Rol = analista o coordinador.",
          "Área = Excelencia Comercial o Digital: el área ES el equipo resolutor.",
          "Opcional: los solicitantes frecuentes con su área y país (si no, los completa el equipo en el primer "
          "ticket y el siguiente ya viene bien)."),
         "Cada analista aparece en Personas con su rol y su equipo."),
    Paso("flujos", "Crear los 6 flujos de Power Automate", "Power Automate (con la cuenta de servicio)", "2-3 h",
         ("1 · Correo → ticket: crea el ticket o lo suma a uno abierto, clasifica y manda el acuse.",
          "2 · Avisos por evento: al analista, al solicitante y la reapertura.",
          "3 · Encuesta de conformidad: «¿Quedó conforme?» con botones; cierra o reabre.",
          "4 · Cierre tácito: lo resuelto sin respuesta en 3 días hábiles.",
          "5 · Vencidos del día: el resumen para los coordinadores.",
          "6 · Export para Power BI: las listas como CSV."),
         "Un «fuera de la oficina» no crea nada; un correo real crea el ticket y su respuesta se suma al mismo.",
         ("powerapps/FLUJOS.md",),
         (("FLUJOS.md", "1 ·"), ("FLUJOS.md", "2 ·"), ("FLUJOS.md", "3 ·"), ("FLUJOS.md", "4 ·"),
          ("FLUJOS.md", "5 ·"), ("FLUJOS.md", "6 ·"))),
    Paso("app", "Armar la app de Power Apps", "Power Apps Studio", "1 día",
         ("Aplicación de lienzo en blanco, formato Tableta, con las listas del sitio como datos.",
          "App → Formulas: pegar entero powerapps/app/Formulas.fx (estados, transiciones, subestados, colores).",
          "Cinco pantallas: Inicio con tarjetas, Nuevo pedido, Mis tickets (chips de estado), Detalle "
          "(conversación + «Datos del ticket») y Consola del equipo."),
         "Como solicitante se crea un pedido y se ve en «Mis tickets»; como analista se toma, se resuelve y se "
         "cambia el estado sólo por las transiciones permitidas.",
         ("powerapps/app/Formulas.fx", "powerapps/APP.md"),
         (("APP.md", "Antes de empezar"), ("APP.md", "1 ·"), ("APP.md", "2 ·"), ("APP.md", "3 ·"),
          ("APP.md", "4 ·"), ("APP.md", "5 ·"))),
    Paso("compartir", "Publicar y compartir la app", "Power Apps", "5 min",
         ("Archivo → Guardar → Publicar.",
          "Compartir con «Todos en Adium» como usuario (no copropietario).",
          "Anclarla en Teams como pestaña del canal del área (opcional)."),
         "Alguien de otra área la abre con su usuario de Microsoft, sin instalar nada."),
    Paso("powerbi", "Programar el export diario y publicar el tablero", "PC del equipo + Power BI", "30 min",
         ("Programador de tareas de Windows, 6:30: scripts\\exportar_powerbi.bat --origen carpeta --csv <carpeta "
          "sincronizada del flujo 6> (o --origen sharepoint con la app de Entra ID).",
          "Abrir powerbi/Tickets_Excelencia_Comercial_y_Digital.pbit, indicar CarpetaDatos, Guardar como .pbix y "
          "Publicar al workspace del área (o el proyecto PBIP a Fabric con Git).",
          "Actualización programada del modelo semántico a las 7:00."),
         "El tablero muestra los tickets de la prueba con sus tiempos y su conformidad.",
         ("powerbi/Tickets_Excelencia_Comercial_y_Digital.pbit",
          "powerbi/Tickets_Excelencia_Comercial_y_Digital_PBIP.zip", "docs/POWERBI.md")),
    Paso("prueba", "Prueba de punta a punta", "Todo junto", "30 min",
         ("Un correo real a la casilla → ticket con tipo, ATC, área terapéutica y unidad de negocio.",
          "Asignarlo, pedir un dato, responder desde la otra cuenta: vuelve a «En curso».",
          "Resolverlo y contestar la encuesta por correo; otro, desde la app.",
          "Correr el export y ver los dos en el tablero."),
         "Los pasos 1 a 7 dan lo esperado. Recién ahí la guía deja de ser «· REVISAR».",
         ("powerapps/APP.md",), (("APP.md", "Probar antes de compartir"),)),
)


def secciones(documento: str) -> dict[str, str]:
    """Las secciones `## ` de un documento de `powerapps/`, por título."""
    ruta = POWERAPPS / documento
    if not ruta.is_file():
        return {}
    partes = re.split(r"^## ", ruta.read_text(encoding="utf-8"), flags=re.MULTILINE)
    salida = {}
    for parte in partes[1:]:
        titulo, _, cuerpo = parte.partition("\n")
        salida[titulo.strip()] = cuerpo.strip().removesuffix("---").strip()
    return salida


def seccion(documento: str, prefijo: str) -> tuple[str, str] | None:
    """(título, cuerpo) de la primera sección cuyo título empieza con `prefijo`."""
    return next(((t, c) for t, c in secciones(documento).items() if t.startswith(prefijo)), None)


def archivo(relativo: str) -> Path:
    return RAIZ / relativo


def faltantes() -> list[str]:
    """Los archivos que la guía ofrece y no están (p. ej. el tablero sin armar)."""
    return sorted({a for p in PASOS for a in p.archivos if not archivo(a).is_file()})
