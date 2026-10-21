"""
La marca de la suite Adium All in One, para que la mesa de tickets se vea
como el informe de al lado.

Los colores son los de `AdiumAllinOne/adium_allinone/marca.py` (contados
sobre el informe corporativo de Adium en Power BI). Se copian los valores y
no el módulo porque este repo tiene que correr solo, sin la suite en disco;
`tests/test_marca.py` los compara contra la suite cuando está al lado.
"""
from __future__ import annotations

from pathlib import Path

NOMBRE = "Tickets · Excelencia Comercial & Digital"
LEMA = "Pedidos por correo · seguimiento · SLA · conformidad · Power BI"

AZUL = "#3B4A5E"          # texto y títulos
BLANCO = "#FFFFFF"
ROJO = "#FF0030"          # el rojo del logo: acento y adorno, NUNCA texto
GRIS = "#627082"          # texto secundario
BORDE = "#E3E8F0"
GRIS_CLARO = "#B8C2CF"    # bordes, NUNCA texto
VERDE = "#12B886"         # relleno de «ok», NUNCA texto
ROJO_ALERTA = "#E03131"
FONDO = "#F2F4F7"
ROJO_TEXTO = "#EB002C"    # botón con letra blanca, y texto sobre blanco
VERDE_TEXTO = "#0D8460"
AMBAR = "#FAB005"         # relleno, con letra AZUL encima

ASSETS = Path(__file__).resolve().parent / "assets"
LOGO = ASSETS / "logo_adium.png"
SIMBOLO = ASSETS / "simbolo_adium.png"

#: Los mismos valores que `[theme]` de `.streamlit/config.toml`.
TEMA = {"base": "light", "primaryColor": ROJO_TEXTO, "backgroundColor": BLANCO,
        "secondaryBackgroundColor": FONDO, "textColor": AZUL, "font": "sans serif"}


def luminancia(hexa: str) -> float:
    h = hexa.lstrip("#")
    canales = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lineal = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def contraste(uno: str, otro: str) -> float:
    a, b = luminancia(uno), luminancia(otro)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


#: Cada texto que la app y los correos pintan, con su fondo. El test exige 4,5:1.
PARES_DE_TEXTO = (
    (AZUL, BLANCO, "texto"), (GRIS, BLANCO, "texto secundario"), (AZUL, FONDO, "barra lateral"),
    (BLANCO, ROJO_TEXTO, "botón y encabezado del correo"), (VERDE_TEXTO, BLANCO, "en SLA"),
    (ROJO_ALERTA, BLANCO, "vencido"), (AZUL, AMBAR, "por vencer"),
)
