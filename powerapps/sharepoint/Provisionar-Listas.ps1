<#
  Crea las listas de la mesa de tickets en un sitio de SharePoint Online.
  GENERADO por scripts/generar_powerplatform.py: no se edita a mano.

  Requisitos: PowerShell 7 y PnP.PowerShell 2.x (Install-Module PnP.PowerShell -Scope CurrentUser),
  una app de Entra ID para PnP (ver https://pnp.github.io/powershell/articles/registerapplication.html)
  y ser propietario del sitio.

  Uso:  ./Provisionar-Listas.ps1 -Sitio https://<tenant>.sharepoint.com/sites/TicketsEC -ClientId <guid>
  Es idempotente: una lista o una columna que ya existe se deja como está.
#>
param(
    [Parameter(Mandatory = $true)] [string] $Sitio,
    [Parameter(Mandatory = $true)] [string] $ClientId
)
$ErrorActionPreference = 'Stop'
Connect-PnPOnline -Url $Sitio -Interactive -ClientId $ClientId
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path

function Asegurar-Lista([string] $Nombre, [string] $Titulo) {
    if (-not (Get-PnPList -Identity $Nombre -ErrorAction SilentlyContinue)) {
        New-PnPList -Title $Nombre -Template GenericList -OnQuickLaunch | Out-Null
        Write-Host "Lista $Nombre creada"
    }
    Set-PnPField -List $Nombre -Identity 'Title' -Values @{ Title = $Titulo } | Out-Null
}
function Asegurar-Columna([string] $Lista, [string] $Interno, [string] $Visible, [string] $Tipo, [string[]] $Opciones) {
    if (Get-PnPField -List $Lista -Identity $Interno -ErrorAction SilentlyContinue) { return }
    if ($Tipo -eq 'DateTime') {
        # Por XML: Add-PnPField crea las fechas SIN hora, y la hora es la mitad del SLA.
        $xml = "<Field Type='DateTime' Format='DateTime' Name='$Interno' StaticName='$Interno' " +
               "DisplayName='$Visible' />"
        Add-PnPFieldFromXml -List $Lista -FieldXml $xml | Out-Null
    } elseif ($Tipo -eq 'Choice') {
        Add-PnPField -List $Lista -InternalName $Interno -DisplayName $Visible -Type Choice -Choices $Opciones -AddToDefaultView | Out-Null
    } else {
        Add-PnPField -List $Lista -InternalName $Interno -DisplayName $Visible -Type $Tipo -AddToDefaultView | Out-Null
    }
}

# ---- Tickets -----------------------------------------------------
Asegurar-Lista 'Tickets' 'Asunto'
Asegurar-Columna 'Tickets' 'Numero' 'Número' 'Text' @()
Asegurar-Columna 'Tickets' 'Descripcion' 'Descripción' 'Note' @()
Asegurar-Columna 'Tickets' 'SolicitanteMail' 'Mail solicitante' 'Text' @()
Asegurar-Columna 'Tickets' 'SolicitanteNombre' 'Solicitante' 'Text' @()
Asegurar-Columna 'Tickets' 'Area' 'Área solicitante' 'Choice' @('Marketing', 'Fuerza de Ventas', 'Gerencia de Filial', 'Dirección Comercial', 'Excelencia Comercial', 'Digital', 'Finanzas', 'Medical Affairs', 'Acceso al Mercado', 'Business Development / Licencias', 'Supply Chain', 'IT', 'Recursos Humanos', 'Sin área')
Asegurar-Columna 'Tickets' 'Pais' 'País' 'Choice' @('Uruguay (HQ)', 'Argentina', 'Bolivia', 'Brasil', 'Centroamérica', 'Chile', 'Colombia', 'Ecuador', 'México', 'Paraguay', 'Perú', 'Venezuela', 'Regional', 'Sin país')
Asegurar-Columna 'Tickets' 'Equipo' 'Equipo resolutor' 'Choice' @('Excelencia Comercial', 'Digital')
Asegurar-Columna 'Tickets' 'Tipo' 'Tipo de ticket' 'Choice' @('Incidente / dato incorrecto', 'Solicitud de permisos', 'Nuevo desarrollo', 'Cambio en tablero existente', 'Pedido de información', 'Pedido digital', 'Capacitación / consulta', 'Otro')
Asegurar-Columna 'Tickets' 'Subtipo' 'Subtipo' 'Text' @()
Asegurar-Columna 'Tickets' 'Prioridad' 'Prioridad' 'Choice' @('Crítica', 'Alta', 'Media', 'Baja')
Asegurar-Columna 'Tickets' 'Canal' 'Canal' 'Choice' @('Correo', 'Portal', 'Manual', 'Teams', 'Teléfono')
Asegurar-Columna 'Tickets' 'Estado' 'Estado' 'Choice' @('Nuevo', 'Asignado', 'En curso', 'En espera del solicitante', 'Resuelto', 'Reabierto', 'Cerrado', 'Cancelado')
Asegurar-Columna 'Tickets' 'Subestado' 'Subestado' 'Text' @()
Asegurar-Columna 'Tickets' 'AnalistaMail' 'Analista (mail)' 'Text' @()
Asegurar-Columna 'Tickets' 'ATC' 'ATC' 'Text' @()
Asegurar-Columna 'Tickets' 'AreaTerapeutica' 'Área terapéutica' 'Choice' @('Metab & Obesidad', 'Cardiovascular', 'Aparato Digestivo', 'Neurociencias', 'Osteo Dolor', 'Salud de la Mujer', 'Salud del Hombre', 'Oncología', 'Otra', 'Transversal / no aplica')
Asegurar-Columna 'Tickets' 'UnidadNegocio' 'Unidad de negocio' 'Choice' @('Cardiovascular', 'Gastro + Hipercol.', 'Metab & Obesidad Lic', 'Metab & Obesidad Pr', 'Neurociencias', 'Osteo Dolor', 'Salud de la Mujer', 'Salud del Hombre', 'Oncología', 'Otra', 'Transversal / no aplica')
Asegurar-Columna 'Tickets' 'Mercado' 'Mercado' 'Text' @()
Asegurar-Columna 'Tickets' 'FuenteDatos' 'Fuente de datos' 'Choice' @('IQVIA', 'Close Up', 'Venta interna / Adaptive', 'Stocking', 'Non Retail', 'MDW / Analysis Services', 'Fabric', 'Otra', 'No aplica')
Asegurar-Columna 'Tickets' 'Tablero' 'Tablero' 'Text' @()
Asegurar-Columna 'Tickets' 'Cc' 'Cc' 'Text' @()
Asegurar-Columna 'Tickets' 'Clasificacion' 'Clasificación' 'Note' @()
Asegurar-Columna 'Tickets' 'MessageId' 'MessageId' 'Text' @()
Asegurar-Columna 'Tickets' 'CreadoEn' 'Creado' 'DateTime' @()
Asegurar-Columna 'Tickets' 'ActualizadoEn' 'Actualizado' 'DateTime' @()
Asegurar-Columna 'Tickets' 'AsignadoEn' 'Asignado' 'DateTime' @()
Asegurar-Columna 'Tickets' 'PrimeraRespuestaEn' 'Primera respuesta' 'DateTime' @()
Asegurar-Columna 'Tickets' 'EnCursoEn' 'En curso' 'DateTime' @()
Asegurar-Columna 'Tickets' 'ResueltoEn' 'Resuelto' 'DateTime' @()
Asegurar-Columna 'Tickets' 'CerradoEn' 'Cerrado' 'DateTime' @()
Asegurar-Columna 'Tickets' 'CanceladoEn' 'Cancelado' 'DateTime' @()
Asegurar-Columna 'Tickets' 'Reaperturas' 'Reaperturas' 'Number' @()
Asegurar-Columna 'Tickets' 'VecesEnEspera' 'Veces en espera' 'Number' @()
Asegurar-Columna 'Tickets' 'Conformidad' 'Conformidad' 'Choice' @('Conforme', 'No conforme', 'Tácita', 'Pendiente', 'Sin encuesta')
Asegurar-Columna 'Tickets' 'CSAT' 'CSAT' 'Number' @()
Asegurar-Columna 'Tickets' 'Resolucion' 'Resolución' 'Note' @()
Asegurar-Columna 'Tickets' 'VenceEn' 'Vence' 'DateTime' @()
Set-PnPField -List 'Tickets' -Identity 'Numero' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'Estado' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'SolicitanteMail' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'AnalistaMail' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'Equipo' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'CreadoEn' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Tickets' -Identity 'Modified' -Values @{ Indexed = $true } | Out-Null

# ---- Eventos -----------------------------------------------------
Asegurar-Lista 'Eventos' 'Tipo de evento'
Asegurar-Columna 'Eventos' 'TicketNumero' 'Ticket' 'Text' @()
Asegurar-Columna 'Eventos' 'En' 'En' 'DateTime' @()
Asegurar-Columna 'Eventos' 'Usuario' 'Usuario' 'Text' @()
Asegurar-Columna 'Eventos' 'EstadoDesde' 'Estado desde' 'Choice' @('Nuevo', 'Asignado', 'En curso', 'En espera del solicitante', 'Resuelto', 'Reabierto', 'Cerrado', 'Cancelado')
Asegurar-Columna 'Eventos' 'EstadoHasta' 'Estado hasta' 'Choice' @('Nuevo', 'Asignado', 'En curso', 'En espera del solicitante', 'Resuelto', 'Reabierto', 'Cerrado', 'Cancelado')
Asegurar-Columna 'Eventos' 'Publico' 'Público' 'Boolean' @()
Asegurar-Columna 'Eventos' 'Detalle' 'Detalle' 'Note' @()
Set-PnPField -List 'Eventos' -Identity 'TicketNumero' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Eventos' -Identity 'Modified' -Values @{ Indexed = $true } | Out-Null

# ---- Encuestas ---------------------------------------------------
Asegurar-Lista 'Encuestas' 'Ticket'
Asegurar-Columna 'Encuestas' 'Ronda' 'Ronda' 'Number' @()
Asegurar-Columna 'Encuestas' 'EnviadaEn' 'Enviada' 'DateTime' @()
Asegurar-Columna 'Encuestas' 'RespondidaEn' 'Respondida' 'DateTime' @()
Asegurar-Columna 'Encuestas' 'Resultado' 'Resultado' 'Choice' @('Pendiente', 'Conforme', 'No conforme', 'Tácita')
Asegurar-Columna 'Encuestas' 'CSAT' 'CSAT' 'Number' @()
Asegurar-Columna 'Encuestas' 'Comentario' 'Comentario' 'Note' @()
Asegurar-Columna 'Encuestas' 'TokenHash' 'Hash del link' 'Text' @()
Set-PnPField -List 'Encuestas' -Identity 'Title' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Encuestas' -Identity 'Modified' -Values @{ Indexed = $true } | Out-Null

# ---- Personas ----------------------------------------------------
Asegurar-Lista 'Personas' 'Nombre'
Asegurar-Columna 'Personas' 'Mail' 'Mail' 'Text' @()
Asegurar-Columna 'Personas' 'Area' 'Área solicitante' 'Choice' @('Marketing', 'Fuerza de Ventas', 'Gerencia de Filial', 'Dirección Comercial', 'Excelencia Comercial', 'Digital', 'Finanzas', 'Medical Affairs', 'Acceso al Mercado', 'Business Development / Licencias', 'Supply Chain', 'IT', 'Recursos Humanos', 'Sin área')
Asegurar-Columna 'Personas' 'Pais' 'País' 'Choice' @('Uruguay (HQ)', 'Argentina', 'Bolivia', 'Brasil', 'Centroamérica', 'Chile', 'Colombia', 'Ecuador', 'México', 'Paraguay', 'Perú', 'Venezuela', 'Regional', 'Sin país')
Asegurar-Columna 'Personas' 'Rol' 'Rol' 'Choice' @('solicitante', 'analista', 'coordinador')
Asegurar-Columna 'Personas' 'Activo' 'Activo' 'Boolean' @()
Set-PnPField -List 'Personas' -Identity 'Mail' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Personas' -Identity 'Modified' -Values @{ Indexed = $true } | Out-Null

# ---- Correos -----------------------------------------------------
Asegurar-Lista 'Correos' 'Message-ID'
Asegurar-Columna 'Correos' 'TicketNumero' 'Ticket' 'Text' @()
Asegurar-Columna 'Correos' 'RecibidoEn' 'Recibido' 'DateTime' @()
Asegurar-Columna 'Correos' 'Remitente' 'Remitente' 'Text' @()
Asegurar-Columna 'Correos' 'Asunto' 'Asunto' 'Text' @()
Asegurar-Columna 'Correos' 'Resultado' 'Resultado' 'Text' @()
Set-PnPField -List 'Correos' -Identity 'Title' -Values @{ Indexed = $true } | Out-Null
Set-PnPField -List 'Correos' -Identity 'Title' -Values @{ EnforceUniqueValues = $true } | Out-Null

# ---- ReglasClasificacion -----------------------------------------
Asegurar-Lista 'ReglasClasificacion' 'Palabra'
Asegurar-Columna 'ReglasClasificacion' 'Tipo' 'Tipo de ticket' 'Choice' @('Incidente / dato incorrecto', 'Solicitud de permisos', 'Nuevo desarrollo', 'Cambio en tablero existente', 'Pedido de información', 'Pedido digital', 'Capacitación / consulta', 'Otro')
Asegurar-Columna 'ReglasClasificacion' 'Peso' 'Peso' 'Number' @()
Asegurar-Columna 'ReglasClasificacion' 'Equipo' 'Equipo resolutor' 'Choice' @('Excelencia Comercial', 'Digital')

# ---- Mercados ----------------------------------------------------
Asegurar-Lista 'Mercados' 'Mercado'
Asegurar-Columna 'Mercados' 'AreaTerapeutica' 'Área terapéutica' 'Text' @()
Asegurar-Columna 'Mercados' 'UnidadNegocio' 'Unidad de negocio' 'Text' @()
Asegurar-Columna 'Mercados' 'ATC' 'ATC' 'Text' @()
Asegurar-Columna 'Mercados' 'CTs' 'Clases terapéuticas' 'Text' @()

# ---- Feriados ----------------------------------------------------
Asegurar-Lista 'Feriados' 'Feriado'
Asegurar-Columna 'Feriados' 'Fecha' 'Fecha' 'DateTime' @()

# ---- Subtipos ----------------------------------------------------
Asegurar-Lista 'Subtipos' 'Subtipo'
Asegurar-Columna 'Subtipos' 'Tipo' 'Tipo de ticket' 'Choice' @('Incidente / dato incorrecto', 'Solicitud de permisos', 'Nuevo desarrollo', 'Cambio en tablero existente', 'Pedido de información', 'Pedido digital', 'Capacitación / consulta', 'Otro')

# ---- SLA ---------------------------------------------------------
Asegurar-Lista 'SLA' 'Tipo de ticket'
Asegurar-Columna 'SLA' 'Prioridad' 'Prioridad' 'Choice' @('Crítica', 'Alta', 'Media', 'Baja')
Asegurar-Columna 'SLA' 'DiasResolucion' 'Días de resolución' 'Number' @()
Asegurar-Columna 'SLA' 'HorasRespuesta' 'Horas a la primera respuesta' 'Number' @()
Asegurar-Columna 'SLA' 'Equipo' 'Equipo resolutor' 'Choice' @('Excelencia Comercial', 'Digital')

# ---- Listas de referencia (se cargan sólo si están vacías) ----------
foreach ($par in @(@('ReglasClasificacion', 'reglas_clasificacion.csv'), @('Subtipos', 'subtipos.csv'),
                   @('SLA', 'sla.csv'), @('Mercados', 'mercados.csv'), @('Feriados', 'feriados.csv'))) {
    $lista, $archivo = $par
    if ((Get-PnPListItem -List $lista -PageSize 1).Count -gt 0) { continue }
    foreach ($fila in Import-Csv -Path (Join-Path $aqui $archivo) -Encoding UTF8) {
        $valores = @{}
        $fila.PSObject.Properties | ForEach-Object { $valores[$_.Name] = $_.Value }
        Add-PnPListItem -List $lista -Values $valores | Out-Null
    }
    Write-Host "$lista cargada desde $archivo"
}
Write-Host 'Listo. Siguiente paso: powerapps/FLUJOS.md'
