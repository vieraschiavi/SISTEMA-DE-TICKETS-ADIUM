# El tablero en Power BI: .pbit, .pbix, PBIP y Fabric

`python powerbi/armar_tablero.py` arma todo con el motor de la suite Adium All
in One (MV DAX Lab), que tiene que estar al lado (`../Power-bi`) o en
`ADIUM_SUITE`.

| Archivo | Qué es | Para qué |
|---|---|---|
| `Tickets_Excelencia_Comercial_y_Digital.pbit` | Plantilla: modelo + 8 páginas, sin datos | Abrir en Desktop y guardar como **.pbix** |
| `Tickets_Excelencia_Comercial_y_Digital_PBIP.zip` / `pbip/` | Proyecto PBIP: modelo semántico (`model.bim`) + reporte | **Fabric**: integración con Git o pipelines de implementación |
| `Tickets_Excelencia_Comercial_y_Digital.xlsx` | Los datos de la demo, con el modelo estrella | Lo que lee la plantilla |
| `Tickets_Excelencia_Comercial_y_Digital.html` | Réplica del tablero con los números calculados por el DAX del modelo | Mirarlo sin Power BI |
| `VERIFICACION.md` | El veredicto del build | Qué se verificó y con qué resultado |

Las ocho páginas son:
1. Resumen ejecutivo.
2. Tickets mensuales.
3. Quién pide: solicitante, área y país.
4. Qué piden: tipo, subtipo, área terapéutica, unidad de negocio, mercado, ATC y fuente.
5. Tiempos y SLA.
6. Equipo: por analista.
7. Conformidad.
8. Backlog y antigüedad.

Los filtros de todas las páginas son equipo resolutor, tipo de ticket, área
solicitante, unidad de negocio y país.

## De .pbit a .pbix para publicar en el servicio corporativo

Un **.pbix con datos sólo lo escribe Power BI Desktop**. El modelo importado va
en un formato binario de Microsoft (VertiPaq comprimido) que ninguna herramienta
externa genera de forma confiable. Por eso se entrega la plantilla, que se
convierte en 30 segundos:

1. Generá los datos: `python scripts/exportar_powerbi.py` (o `--origen sharepoint`).
2. Abrí el `.pbit` en Power BI Desktop. Va a pedir **CarpetaDatos**: es la
   carpeta donde está el Excel, con la barra final (`C:\TicketsEC\datos\powerbi\`).
3. **Archivo → Guardar como → .pbix.**
4. **Publicar** → el workspace del área.
5. En el servicio, en la configuración del modelo semántico, completá las
   credenciales y la **actualización programada** (por ejemplo a las 7:00,
   después del export de las 6:30).
   - Si el Excel está en una carpeta local, hace falta la **puerta de enlace**
     (*on-premises data gateway*) de IT.
   - Si está en SharePoint, Power BI lo lee sin puerta de enlace: cambiá el
     origen por *SharePoint Online* y apuntalo al archivo.

## A Fabric

**Con Git (recomendado):**
1. Subí la carpeta `powerbi/pbip/` a un repo de Azure DevOps o GitHub. Cada
   build la regenera.
2. En el workspace de Fabric: *Configuración del área de trabajo → Integración
   de Git* → conectar el repo y la carpeta. Fabric crea el modelo semántico y
   el informe.
3. Desde ahí, los **pipelines de implementación** lo pasan de desarrollo a
   producción.

**Por API** (con un token del usuario, que no se guarda):
```bash
export TICKETS_FABRIC_TOKEN=$(az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv)
python powerbi/publicar_fabric.py --ver                       # qué mandaría
python powerbi/publicar_fabric.py --workspace <id-del-workspace>
```

**Los datos en Fabric:** el paso natural es un Lakehouse.
1. Un *notebook* del workspace instala este paquete (`tickets_ec/`, que sólo
   usa la biblioteca estándar).
2. Corre `sharepoint.cargar(...)` y `exportar.tablas(...)`.
3. Escribe las cuatro tablas como Delta.

El modelo semántico pasa de leer el Excel a leer el Lakehouse con Direct Lake.
Las medidas y las páginas son las mismas.

## Qué verifica el build antes de entregar

1. **El archivo:** los chequeos de `dxl.verificacion` sobre el `.pbit` y sobre
   el proyecto PBIP escritos. Se verifica lo que se escribió, no el modelo en
   memoria.
2. **Los números:** cada medida con KPI, contra `tickets_ec.indicadores`. Se
   compara el total, los últimos seis meses, el primero y cada equipo
   resolutor. Son 220 comparaciones.
3. **Los tipos de columna:** cada columna numérica o de fecha tiene que tener
   su tipo en el modelo. El lector del motor infiere el tipo con una muestra
   de 500 filas; si arriba vienen vacías, como «Días abierto», la columna
   quedaría como texto y un promedio sobre texto es un error en Power BI. El
   build la corrige y lo anota.
4. **Los filtros:** ningún segmentador con un solo valor.
5. **El analizador del motor** (las 26 reglas): las medidas usan `KEEPFILTERS`
   y `CALCULATETABLE` y tienen descripción, para que el analizador no tenga
   nada que acusar.

Si algo falla, el `.pbit` sale con «· REVISAR» en el nombre y el script
termina en 1.
