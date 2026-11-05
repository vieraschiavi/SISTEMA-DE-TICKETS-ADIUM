"""
La documentación del proyecto, para presentarlo, generada desde el programa:

    python scripts/documentar.py

Escribe `docs/PROYECTO.md` (para leer en GitHub) y `docs/PROYECTO.html` (una
sola página con la marca de Adium, para proyectar o imprimir a PDF).

No se escribe a mano porque se desactualiza a la semana. Los estados, los
tipos con sus plazos, los indicadores, las páginas del tablero, los pasos de
la guía, los módulos y la cantidad de pruebas salen del código; el historial
sale de `docs/CAMBIOS.md`. `tests/test_documentacion.py` falla si lo
commiteado no es lo que este script genera: cada vez que el programa cambia,
la documentación se regenera en el mismo commit.
"""
from __future__ import annotations

import ast
import html
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "powerbi")]

import medidas  # noqa: E402

from tickets_ec import __version__, guia  # noqa: E402
from tickets_ec import catalogos as C  # noqa: E402
from tickets_ec import freshservice as FS  # noqa: E402
from tickets_ec import marca as M  # noqa: E402
from tickets_ec.config import Config  # noqa: E402

DESTINO_MD = RAIZ / "docs" / "PROYECTO.md"
DESTINO_HTML = RAIZ / "docs" / "PROYECTO.html"

#: Cómo entra un pedido por cada canal. Un canal nuevo sin su línea acá rompe un test.
CANALES = {
    "Correo": "Un correo a la casilla del área. La respuesta del solicitante se suma al mismo ticket por el número "
              "del asunto; los automáticos («fuera de la oficina») no abren nada.",
    "Portal": "El portal de la mesa (🌐 Portal), en la app o en la suite, con la cuenta de Adium: Enviar un ticket, "
              "Mis tickets y la conformidad.",
    "Manual": "El equipo lo carga en «➕ Nuevo pedido» cuando el pedido llegó de palabra.",
    "Teams": "El equipo lo carga desde una conversación de Teams.",
    "Teléfono": "El equipo lo carga desde una llamada.",
    "FreshService": "La opción de la mesa en el portal de IT («Reportería Excelencia Comercial»); el estado y la "
                    "resolución vuelven a FreshService. Apagado hasta que IT sume la opción.",
}


# ==========================================================================
# El contenido, como bloques: los mismos para Markdown y para HTML
# ==========================================================================
def _modulos() -> list[list[str]]:
    filas = []
    for ruta in sorted((RAIZ / "tickets_ec").glob("*.py")):
        if ruta.name == "__init__.py":
            continue
        doc = ast.get_docstring(ast.parse(ruta.read_text(encoding="utf-8"))) or ""
        primera = " ".join(doc.strip().split("\n\n")[0].split())
        filas.append([f"`{ruta.name}`", primera])
    return filas


def _paginas_app() -> list[str]:
    texto = (RAIZ / "app" / "app.py").read_text(encoding="utf-8")
    final = texto[texto.rindex('{"🏠 Inicio"'):]
    return re.findall(r'"([^"]+)":\s*\w+', final)


def _tests() -> tuple[int, int]:
    archivos = sorted((RAIZ / "tests").glob("test_*.py"))
    return len(archivos), sum(len(re.findall(r"^def test_", a.read_text(encoding="utf-8"), re.M)) for a in archivos)


def _cambios() -> list[tuple[str, list[str]]]:
    texto = (RAIZ / "docs" / "CAMBIOS.md").read_text(encoding="utf-8")
    versiones = []
    for bloque in re.split(r"^## ", texto, flags=re.M)[1:]:
        titulo, _, cuerpo = bloque.partition("\n")
        items = [" ".join(i.split()) for i in re.split(r"^- ", cuerpo.strip(), flags=re.M) if i.strip()]
        versiones.append((titulo.strip(), items))
    return versiones


def version_documentada() -> str:
    return _cambios()[0][0].split(" ")[0]


def bloques() -> list[tuple]:
    cfg = Config()
    cambios = _cambios()
    fecha = cambios[0][0].split("·")[1].strip()
    n_archivos, n_tests = _tests()
    b: list[tuple] = [
        ("portada", M.NOMBRE, f"Versión {__version__} · {fecha}", M.LEMA),
        ("h2", "En una página"),
        ("ul", [
            "**Qué resuelve.** Que cada pedido a Excelencia Comercial y a Digital tenga dueño, plazo y respuesta, "
            "y que se pueda medir: cuántos entran, quién tiene cada uno, cuánto tardan y si el que pidió quedó "
            "conforme.",
            "**Qué es.** Una mesa de pedidos: cada pedido es un ticket con número, solicitante, área, tipo, "
            "unidad de negocio y ATC, analista, estados con fecha y hora, plazo en horas hábiles y encuesta de "
            "conformidad.",
            f"**Cómo entra.** Por {len(C.CANALES)} canales que terminan en el mismo ticket: la casilla, el portal "
            "propio, FreshService de IT, Power Apps o el equipo a mano.",
            "**Cómo se mide.** Un tablero de Power BI con cada indicador verificado contra la app antes de "
            "entregarse, listo para publicar en el workspace del área o en Fabric.",
            "**Dónde corre.** En la PC de cada integrante (sola o dentro de la suite Adium All in One) sobre las "
            "mismas listas de SharePoint, o entera en Microsoft 365 (Power Apps + Power Automate).",
        ]),
        ("h2", "Cómo entra un pedido"),
        ("table", ["Canal", "Cómo entra"], [[c, CANALES[c]] for c in C.CANALES]),
        ("p", "Todos los canales crean el mismo ticket, con el mismo número (`EC-00042`), la misma clasificación "
              "automática, el mismo plazo y la misma encuesta."),
        ("h2", "Qué le pasa a un pedido"),
        ("table", ["Estado", "Subestados", "Desde acá el equipo lo pasa a", "Reloj del plazo"],
         [[e, ", ".join(C.SUBESTADOS.get(e, ())),
           ", ".join(sorted(C.TRANSICIONES.get(e, ()), key=C.ORDEN_ESTADO.get)) or
           ("lo decide el solicitante (o el cierre tácito)" if e == C.RESUELTO else "—"),
           "detenido" if e in C.RELOJ_DETENIDO else ("—" if e in C.FINALES else "corre")] for e in C.ESTADOS]),
        ("p", f"Mientras se espera al solicitante, el reloj se detiene. Al resolverlo, el solicitante recibe "
              f"«¿Quedó conforme?» con una nota de 1 a 5. Si dice que no, el ticket se reabre; si no contesta en "
              f"{cfg.dias_conformidad_tacita} días hábiles, se cierra con conformidad tácita. El día hábil va de "
              f"{cfg.hora_inicio} a {cfg.hora_fin} h, sin feriados de Uruguay."),
        ("h2", "Qué se puede pedir y en cuánto tiempo"),
        ("table", ["Tipo de pedido", "Lo atiende", "Prioridad habitual", "Días hábiles (Crítica · Alta · Media · Baja)",
                   "Por ejemplo"],
         [[t.nombre, t.equipo, t.prioridad, " · ".join(str(d) for d in t.dias),
           ", ".join(s for s in t.subtipos if s != "Sin detalle")] for t in C.TIPOS]),
        ("p", "Primera respuesta del equipo: " + " · ".join(f"{p.nombre} {p.horas_respuesta:g} h"
                                                            for p in C.PRIORIDADES) + " hábiles."),
        ("h2", "Clasificación automática"),
        ("ul", [
            "**Tipo, subtipo y prioridad**, por las palabras del asunto y la descripción (con el porqué, a la "
            "vista del equipo); las urgencias suben la prioridad.",
            "**Equipo resolutor:** " + " o ".join(C.EQUIPOS) + "; lo digital (CRM, Veeva, mailing, landing…) va "
            "a Digital, y un pedido se puede derivar entre los dos.",
            "**ATC y mercado conformado de HQ**, y de ahí el **área terapéutica** (" + ", ".join(C.AREAS_TERAPEUTICAS)
            + ") y la **unidad de negocio** (" + ", ".join(C.UNIDADES_NEGOCIO) + ").",
            "**Área y país** del solicitante, por el directorio y el dominio de su correo; **fuente de datos** ("
            + ", ".join(C.FUENTES) + ").",
        ]),
        ("h2", "Quién hace qué"),
        ("table", ["Rol", "Puede"], [
            ["Coordinador", "Todo: asignar y reasignar, derivar, dar de alta y de baja integrantes."],
            ["Analista", "Tomar lo que está sin asignar, trabajar y resolver lo suyo, dejar notas en cualquier "
                         "ticket, leer la casilla."],
            ["Cualquier cuenta de Adium", "Pedir por el portal, la casilla, FreshService o Power Apps, seguir sus "
                                          "pedidos y dar la conformidad."]]),
        ("p", "En el modo compartido el rol sale de la lista **Personas**. La app nunca ve una contraseña: el "
              "ingreso es la página de Microsoft, con el MFA de Adium."),
        ("h2", "Indicadores"),
    ]
    carpetas: dict[str, list[list[str]]] = {}
    for m in medidas.MEDIDAS:
        if m.get("descripcion") and "Notas" not in m["carpeta"]:     # las notas y signos de las tarjetas, no
            carpetas.setdefault(m["carpeta"], []).append([m["nombre"], m["descripcion"]])
    for carpeta, filas in carpetas.items():
        b.append(("h3", carpeta.split("·", 1)[-1].strip()))
        b.append(("table", ["Indicador", "Qué mide"], filas))
    b += [
        ("h2", f"El tablero de Power BI ({len(medidas.PAGINAS)} páginas)"),
        ("table", ["Página", "La pregunta que contesta"], [[p["titulo"], p["pregunta"]] for p in medidas.PAGINAS]),
        ("p", "Cada indicador del tablero tiene su gemelo en la app (`indicadores.kpis`): el armado del `.pbit` "
              "compara los dos y no entrega si difieren. Sale como `.pbit` (se abre en Power BI Desktop y se "
              "publica), como proyecto PBIP para Fabric con Git, o se publica por API."),
        ("h2", "Dónde corre"),
        ("table", ["Modo", "Para qué", "Dónde viven los tickets"], [
            ["Local", "Una PC sola, el piloto o la demo", "Un SQLite en esa PC"],
            ["Compartido", "Cada integrante en su PC, con su cuenta de Adium", "Las listas de SharePoint de la mesa "
                                                                             "(cada PC con su copia)"],
            ["Power Platform", "Todo en Microsoft 365, sin instalar nada", "Las mismas listas de SharePoint"]]),
        ("p", "En el modo compartido, cada escritura va primero a la lista con la versión que esa PC leyó: si dos "
              "personas tocan el mismo ticket, la segunda recibe «otro integrante lo cambió» y nada se pisa. El "
              "mismo correo leído por dos PCs abre un solo ticket."),
        ("h3", "Llevarla a Power Platform"),
        ("ol", [f"**{p.titulo}** — {p.donde} · {p.tiempo}" for p in guia.PASOS]),
        ("h3", "FreshService de IT"),
        ("p", "«Incidencia en = Excelencia Comercial» es un pedido del área que resuelve IT. Para los pedidos A "
              "la mesa, IT suma una opción propia y el conector (apagado por defecto) los trae; el estado vuelve:"),
        ("table", ["En la mesa", "En FreshService"],
         [[e, FS.NOMBRE_ESTADO[FS.A_FRESHSERVICE[e]]] for e in C.ESTADOS]),
        ("h2", "Seguridad y datos"),
        ("ul", [
            "Los conectores (envío de correo, FreshService) salen **apagados**; los secretos van sólo por "
            "variables de entorno (`TICKETS_*`) y un `.toml` con un secreto no arranca.",
            "Ninguna contraseña pasa por la app: el ingreso es el de Microsoft y el token vive en memoria.",
            "En el portal cada uno ve sólo sus pedidos y los que lleva en copia; el filtro está en el motor.",
            "Lo que escribe el solicitante se escapa antes de entrar a un correo o a una pantalla.",
            "La demo es 100 % sintética: personas ficticias en un dominio que no existe.",
        ]),
        ("h2", "El programa por dentro"),
        ("table", ["Módulo", "Qué hace"], _modulos()),
        ("p", "La app (Streamlit) tiene estas páginas: " + " · ".join(_paginas_app()) + ". Todo lo que cambia un "
              "ticket pasa por `servicio.Mesa`: la app, el portal, la casilla, FreshService y la demo usan las "
              "mismas reglas."),
        ("p", f"**{n_tests} pruebas** en {n_archivos} archivos (`python -m pytest -q tests`), el linter "
              "(`ruff check .`) y una recorrida de la app de verdad en Chromium (`python scripts/e2e_ui.py`)."),
        ("h2", "Qué falta probar en el tenant de Adium"),
        ("ul", [
            "El modo compartido con dos cuentas reales (está probado contra un doble de SharePoint): "
            "`docs/EQUIPO.md`.",
            "La opción de FreshService y su API key (probado contra un doble de la API v2): `docs/PORTAL.md`.",
            "Los flujos de Power Automate y la app de Power Apps: la guía de Power Platform.",
        ]),
        ("h2", "Historial de versiones"),
    ]
    for titulo, items in cambios:
        b.append(("h3", titulo))
        b.append(("ul", items))
    return b


# ==========================================================================
# Markdown
# ==========================================================================
def _celda(t: str) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def a_markdown(bs: list[tuple]) -> str:
    out: list[str] = []
    for blk in bs:
        tipo = blk[0]
        if tipo == "portada":
            out += [f"# {blk[1]}", "", f"**{blk[2]}** — {blk[3]}", "",
                    "> Generado por `python scripts/documentar.py` desde el programa: no se edita a mano. "
                    "La versión para proyectar es `docs/PROYECTO.html`.", ""]
        elif tipo in ("h2", "h3"):
            out += [("## " if tipo == "h2" else "### ") + blk[1], ""]
        elif tipo == "p":
            out += [blk[1], ""]
        elif tipo == "ul":
            out += [f"- {i}" for i in blk[1]] + [""]
        elif tipo == "ol":
            out += [f"{n}. {i}" for n, i in enumerate(blk[1], 1)] + [""]
        elif tipo == "table":
            out += ["| " + " | ".join(blk[1]) + " |", "|" + "---|" * len(blk[1])]
            out += ["| " + " | ".join(_celda(c) for c in fila) + " |" for fila in blk[2]] + [""]
    return "\n".join(out).rstrip() + "\n"


# ==========================================================================
# HTML (una página, con la marca de Adium, que se proyecta o se imprime)
# ==========================================================================
def _en_linea(texto: str) -> str:
    t = html.escape(str(texto), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", t)


def a_html(bs: list[tuple]) -> str:
    cuerpo: list[str] = []
    indice: list[str] = []
    n = 0
    for blk in bs:
        tipo = blk[0]
        if tipo == "portada":
            cuerpo.append(f"<header><div class='marca'></div><h1>{_en_linea(blk[1])}</h1>"
                          f"<p class='version'>{_en_linea(blk[2])}</p><p class='lema'>{_en_linea(blk[3])}</p>"
                          "<nav id='indice'></nav></header>")
        elif tipo == "h2":
            n += 1
            indice.append(f"<a href='#s{n}'>{_en_linea(blk[1])}</a>")
            cuerpo.append(f"<h2 id='s{n}'>{_en_linea(blk[1])}</h2>")
        elif tipo == "h3":
            cuerpo.append(f"<h3>{_en_linea(blk[1])}</h3>")
        elif tipo == "p":
            cuerpo.append(f"<p>{_en_linea(blk[1])}</p>")
        elif tipo in ("ul", "ol"):
            cuerpo.append(f"<{tipo}>" + "".join(f"<li>{_en_linea(i)}</li>" for i in blk[1]) + f"</{tipo}>")
        elif tipo == "table":
            cabeza = "".join(f"<th>{_en_linea(h)}</th>" for h in blk[1])
            filas = "".join("<tr>" + "".join(f"<td>{_en_linea(c)}</td>" for c in fila) + "</tr>" for fila in blk[2])
            cuerpo.append(f"<div class='tabla'><table><thead><tr>{cabeza}</tr></thead><tbody>{filas}</tbody></table></div>")
    pagina = "\n".join(cuerpo).replace("<nav id='indice'></nav>", "<nav id='indice'>" + "".join(indice) + "</nav>")
    titulo = html.escape(bs[0][1])
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<style>
:root {{ --azul:{M.AZUL}; --rojo:{M.ROJO_TEXTO}; --gris:{M.GRIS}; --borde:{M.BORDE}; --fondo:{M.FONDO}; --blanco:{M.BLANCO}; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--fondo); color:var(--azul); font:15px/1.55 "Segoe UI", Inter, system-ui, sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 16px 64px; }}
header {{ background:var(--blanco); border:1px solid var(--borde); border-radius:12px; padding:28px 28px 20px;
          border-top:6px solid var(--rojo); }}
h1 {{ margin:0 0 6px; font-size:30px; }}
.version {{ margin:0; font-weight:600; }}
.lema {{ margin:4px 0 16px; color:var(--gris); }}
nav {{ display:flex; flex-wrap:wrap; gap:6px 14px; font-size:13px; }}
nav a {{ color:var(--rojo); text-decoration:none; }}
h2 {{ margin:36px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--borde); font-size:22px; }}
h3 {{ margin:22px 0 8px; font-size:17px; }}
code {{ background:var(--blanco); border:1px solid var(--borde); border-radius:4px; padding:0 4px; font-size:13px; }}
.tabla {{ overflow-x:auto; background:var(--blanco); border:1px solid var(--borde); border-radius:8px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th {{ background:var(--azul); color:var(--blanco); text-align:left; padding:8px 10px; font-weight:600; }}
td {{ padding:7px 10px; border-top:1px solid var(--borde); vertical-align:top; }}
tbody tr:nth-child(even) td {{ background:var(--fondo); }}
li {{ margin:4px 0; }}
@media print {{ body {{ background:#fff; }} h2 {{ break-before:page; }} .tabla {{ overflow:visible; }} nav {{ display:none; }} }}
</style></head>
<body><main>
{pagina}
<p style="color:var(--gris);font-size:12px;margin-top:40px">Generado por <code>python scripts/documentar.py</code>
desde el programa. No se edita a mano.</p>
</main></body></html>
"""


def archivos() -> dict[Path, str]:
    bs = bloques()
    return {DESTINO_MD: a_markdown(bs), DESTINO_HTML: a_html(bs)}


def main() -> int:
    for ruta, contenido in archivos().items():
        ruta.write_text(contenido, encoding="utf-8")
        print(ruta.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
