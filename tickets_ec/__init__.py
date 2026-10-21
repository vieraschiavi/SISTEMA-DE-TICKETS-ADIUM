"""
Tickets · Excelencia Comercial (Adium).

Mesa de pedidos por correo: cada mail a la casilla del área es un ticket con
solicitante, área, tipo, prioridad, analista, estados con fecha y hora, SLA
en horas hábiles y una encuesta de conformidad al resolverlo. Todo se exporta
a un modelo estrella que lee el tablero de Power BI.

El motor (este paquete) usa sólo la biblioteca estándar: se importa y se
prueba sin Streamlit, sin pandas y sin red.
"""

__version__ = "1.0.0"
