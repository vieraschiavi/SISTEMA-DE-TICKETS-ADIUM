"""
Genera el paquete de Power Platform desde los catálogos de la mesa:

    python scripts/generar_powerplatform.py

Escribe en `powerapps/sharepoint/`:

* `Provisionar-Listas.ps1` — PnP PowerShell que crea las nueve listas con sus
  columnas, opciones e índices, y carga las listas de referencia.
* `esquema.json` — las mismas listas, para leerlas sin PowerShell.
* `reglas_clasificacion.csv`, `subtipos.csv`, `sla.csv`, `mercados.csv`,
  `feriados.csv` — los catálogos que usan los flujos y la app.

Se genera, no se aplica: el script lo corre una persona con permisos sobre
el sitio, después de leerlo. Un test verifica que lo commiteado esté al día
con `catalogos.py` (si alguien agrega un tipo y no regenera, el test lo dice).
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tickets_ec import catalogos as C  # noqa: E402
from tickets_ec import clasificador  # noqa: E402
from tickets_ec.config import Config  # noqa: E402
from tickets_ec.sharepoint import INDEXADAS, LISTAS, TITULOS, VISIBLES  # noqa: E402

DESTINO = RAIZ / "powerapps" / "sharepoint"


def _csv(filas: list[dict]) -> str:
    salida = io.StringIO()
    w = csv.DictWriter(salida, fieldnames=list(filas[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(filas)
    return salida.getvalue()


def catalogos() -> dict[str, str]:
    reglas = []
    for t in C.TIPOS:
        for palabra in t.palabras:
            reglas.append({"Title": palabra, "Tipo": t.nombre, "Peso": len(palabra.split()), "Equipo": t.equipo})
    for palabra in C.PALABRAS_DIGITAL:
        if not any(r["Title"] == palabra for r in reglas):
            reglas.append({"Title": palabra, "Tipo": "Pedido digital", "Peso": 1, "Equipo": C.DIGITAL})
    subtipos = [{"Title": s, "Tipo": t.nombre} for t in C.TIPOS for s in t.subtipos]
    sla = [{"Title": t.nombre, "Prioridad": p.nombre, "DiasResolucion": t.dias[p.orden - 1],
            "HorasRespuesta": p.horas_respuesta, "Equipo": t.equipo} for t in C.TIPOS for p in C.PRIORIDADES]
    mercados = [{"Title": m["mercado"], "AreaTerapeutica": m["area_terapeutica"],
                 "UnidadNegocio": C.unidad_negocio(m["atc"], m["mercado"]), "ATC": m["atc"], "CTs": m["cts"]}
                for m in clasificador.mercados()]
    feriados = [{"Title": "Feriado (Uruguay)", "Fecha": d.isoformat()} for d in Config().feriados]
    return {"reglas_clasificacion.csv": _csv(reglas), "subtipos.csv": _csv(subtipos), "sla.csv": _csv(sla),
            "mercados.csv": _csv(mercados), "feriados.csv": _csv(feriados)}


def _ps(texto: str) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def powershell() -> str:
    lineas = [
        "<#",
        "  Crea las listas de la mesa de tickets en un sitio de SharePoint Online.",
        "  GENERADO por scripts/generar_powerplatform.py: no se edita a mano.",
        "",
        "  Requisitos: PowerShell 7 y PnP.PowerShell 2.x (Install-Module PnP.PowerShell -Scope CurrentUser),",
        "  una app de Entra ID para PnP (ver https://pnp.github.io/powershell/articles/registerapplication.html)",
        "  y ser propietario del sitio.",
        "",
        "  Uso:  ./Provisionar-Listas.ps1 -Sitio https://<tenant>.sharepoint.com/sites/TicketsEC -ClientId <guid>",
        "  Es idempotente: una lista o una columna que ya existe se deja como está.",
        "#>",
        "param(",
        "    [Parameter(Mandatory = $true)] [string] $Sitio,",
        "    [Parameter(Mandatory = $true)] [string] $ClientId",
        ")",
        "$ErrorActionPreference = 'Stop'",
        "Connect-PnPOnline -Url $Sitio -Interactive -ClientId $ClientId",
        "$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path",
        "",
        "function Asegurar-Lista([string] $Nombre, [string] $Titulo) {",
        "    if (-not (Get-PnPList -Identity $Nombre -ErrorAction SilentlyContinue)) {",
        "        New-PnPList -Title $Nombre -Template GenericList -OnQuickLaunch | Out-Null",
        "        Write-Host \"Lista $Nombre creada\"",
        "    }",
        "    Set-PnPField -List $Nombre -Identity 'Title' -Values @{ Title = $Titulo } | Out-Null",
        "}",
        "function Asegurar-Columna([string] $Lista, [string] $Interno, [string] $Visible, [string] $Tipo,"
        " [string[]] $Opciones) {",
        "    if (Get-PnPField -List $Lista -Identity $Interno -ErrorAction SilentlyContinue) { return }",
        "    if ($Tipo -eq 'DateTime') {",
        "        # Por XML: Add-PnPField crea las fechas SIN hora, y la hora es la mitad del SLA.",
        "        $xml = \"<Field Type='DateTime' Format='DateTime' Name='$Interno' StaticName='$Interno' \" +",
        "               \"DisplayName='$Visible' />\"",
        "        Add-PnPFieldFromXml -List $Lista -FieldXml $xml | Out-Null",
        "    } elseif ($Tipo -eq 'Choice') {",
        "        Add-PnPField -List $Lista -InternalName $Interno -DisplayName $Visible -Type Choice "
        "-Choices $Opciones -AddToDefaultView | Out-Null",
        "    } else {",
        "        Add-PnPField -List $Lista -InternalName $Interno -DisplayName $Visible -Type $Tipo "
        "-AddToDefaultView | Out-Null",
        "    }",
        "}",
        "",
    ]
    for lista, columnas in LISTAS.items():
        lineas.append(f"# ---- {lista} " + "-" * (60 - len(lista)))
        lineas.append(f"Asegurar-Lista {_ps(lista)} {_ps(TITULOS[lista])}")
        for interno, tipo, opciones, _col in columnas:
            if interno == "Title":
                continue
            opc = ("@(" + ", ".join(_ps(o) for o in opciones) + ")") if opciones else "@()"
            lineas.append(f"Asegurar-Columna {_ps(lista)} {_ps(interno)} {_ps(VISIBLES.get(interno, interno))} "
                          f"{_ps(tipo)} {opc}")
        for col in INDEXADAS.get(lista, ()):
            lineas.append(f"Set-PnPField -List {_ps(lista)} -Identity {_ps(col)} -Values @{{ Indexed = $true }} "
                          "| Out-Null")
        lineas.append("")
    lineas += [
        "# ---- Listas de referencia (se cargan sólo si están vacías) ----------",
        "foreach ($par in @(@('ReglasClasificacion', 'reglas_clasificacion.csv'), @('Subtipos', 'subtipos.csv'),",
        "                   @('SLA', 'sla.csv'), @('Mercados', 'mercados.csv'), @('Feriados', 'feriados.csv'))) {",
        "    $lista, $archivo = $par",
        "    if ((Get-PnPListItem -List $lista -PageSize 1).Count -gt 0) { continue }",
        "    foreach ($fila in Import-Csv -Path (Join-Path $aqui $archivo) -Encoding UTF8) {",
        "        $valores = @{}",
        "        $fila.PSObject.Properties | ForEach-Object { $valores[$_.Name] = $_.Value }",
        "        Add-PnPListItem -List $lista -Values $valores | Out-Null",
        "    }",
        "    Write-Host \"$lista cargada desde $archivo\"",
        "}",
        "Write-Host 'Listo. Siguiente paso: powerapps/FLUJOS.md'",
        "",
    ]
    return "\n".join(lineas)


def _fx(texto: str) -> str:
    return '"' + str(texto).replace('"', '""') + '"'


def formulas() -> str:
    """Las fórmulas con nombre de la app (App → Formulas), desde los catálogos."""
    from tickets_ec import marca as M
    colores = {C.NUEVO: (M.AZUL, M.BLANCO), C.ASIGNADO: (M.GRIS, M.BLANCO), C.EN_CURSO: (M.AMBAR, M.AZUL),
               C.EN_ESPERA: (M.AMBAR, M.AZUL), C.RESUELTO: (M.VERDE_TEXTO, M.BLANCO),
               C.REABIERTO: (M.ROJO_TEXTO, M.BLANCO), C.CERRADO: (M.BORDE, M.AZUL), C.CANCELADO: (M.BORDE, M.AZUL)}
    trans = ",\n    ".join(f"{{Desde: {_fx(d)}, Hacia: {_fx(h)}}}" for d, hs in C.TRANSICIONES.items()
                           for h in sorted(hs, key=C.ORDEN_ESTADO.get))
    subs = ",\n    ".join(f"{{Estado: {_fx(e)}, Subestado: {_fx(s)}}}" for e, ss in C.SUBESTADOS.items() for s in ss)
    cols = ",\n    ".join(f"{{Estado: {_fx(e)}, Fondo: {_fx(f)}, Letra: {_fx(c)}}}" for e, (f, c) in colores.items())
    lista = lambda vals: "[" + ", ".join(_fx(v) for v in vals) + "]"  # noqa: E731
    return f"""// GENERADO por scripts/generar_powerplatform.py desde tickets_ec/catalogos.py: no se edita a mano.
// Pegar en Power Apps Studio → App → propiedad Formulas (fórmulas con nombre).

Yo = Lower(User().Email);
MiPersona = LookUp(Personas, Mail = Yo);
EsEquipo = !IsBlank(MiPersona) && (MiPersona.Rol.Value = "analista" || MiPersona.Rol.Value = "coordinador");
Prefijo = "{Config().prefijo}";

// Colores de la marca (tickets_ec/marca.py)
Azul = ColorValue("{M.AZUL}");
Rojo = ColorValue("{M.ROJO_TEXTO}");
Gris = ColorValue("{M.GRIS}");
Fondo = ColorValue("{M.FONDO}");
Borde = ColorValue("{M.BORDE}");

// Estados
Pendientes = {lista(sorted(C.PENDIENTES_EQUIPO, key=C.ORDEN_ESTADO.get))};
Finales = {lista(sorted(C.FINALES, key=C.ORDEN_ESTADO.get))};
// Lo que puede hacer el EQUIPO. Resuelto → Cerrado/Reabierto lo decide el solicitante.
Transiciones = Table(
    {trans}
);
SubestadosPorEstado = Table(
    {subs}
);
ColoresEstado = Table(
    {cols}
);
Equipos = {lista(C.EQUIPOS)};
UnidadesNegocio = {lista(C.UNIDADES_NEGOCIO)};
AreasTerapeuticas = {lista(C.AREAS_TERAPEUTICAS)};
HoraFin = {Config().hora_fin};
DiasTacita = {Config().dias_conformidad_tacita};
"""


def esquema() -> str:
    return json.dumps({lista: [{"interno": i, "visible": TITULOS[lista] if i == "Title" else VISIBLES.get(i, i),
                                "tipo": t, "opciones": list(o) if o else None} for i, t, o, _c in cols]
                       for lista, cols in LISTAS.items()}, ensure_ascii=False, indent=2) + "\n"


def archivos() -> dict[str, str]:
    return {"Provisionar-Listas.ps1": powershell(), "esquema.json": esquema(), "../app/Formulas.fx": formulas(),
            **catalogos()}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in archivos().items():
        ruta = (DESTINO / nombre).resolve()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8", newline="\n")
        print(ruta.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
