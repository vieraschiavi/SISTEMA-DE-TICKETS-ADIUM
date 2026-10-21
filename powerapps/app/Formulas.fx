// GENERADO por scripts/generar_powerplatform.py desde tickets_ec/catalogos.py: no se edita a mano.
// Pegar en Power Apps Studio → App → propiedad Formulas (fórmulas con nombre).

Yo = Lower(User().Email);
MiPersona = LookUp(Personas, Mail = Yo);
EsEquipo = !IsBlank(MiPersona) && (MiPersona.Rol.Value = "analista" || MiPersona.Rol.Value = "coordinador");
Prefijo = "EC";

// Colores de la marca (tickets_ec/marca.py)
Azul = ColorValue("#3B4A5E");
Rojo = ColorValue("#EB002C");
Gris = ColorValue("#627082");
Fondo = ColorValue("#F2F4F7");
Borde = ColorValue("#E3E8F0");

// Estados
Pendientes = ["Nuevo", "Asignado", "En curso", "Reabierto"];
Finales = ["Cerrado", "Cancelado"];
// Lo que puede hacer el EQUIPO. Resuelto → Cerrado/Reabierto lo decide el solicitante.
Transiciones = Table(
    {Desde: "Nuevo", Hacia: "Asignado"},
    {Desde: "Nuevo", Hacia: "En curso"},
    {Desde: "Nuevo", Hacia: "En espera del solicitante"},
    {Desde: "Nuevo", Hacia: "Resuelto"},
    {Desde: "Nuevo", Hacia: "Cancelado"},
    {Desde: "Asignado", Hacia: "En curso"},
    {Desde: "Asignado", Hacia: "En espera del solicitante"},
    {Desde: "Asignado", Hacia: "Resuelto"},
    {Desde: "Asignado", Hacia: "Cancelado"},
    {Desde: "En curso", Hacia: "En espera del solicitante"},
    {Desde: "En curso", Hacia: "Resuelto"},
    {Desde: "En curso", Hacia: "Cancelado"},
    {Desde: "En espera del solicitante", Hacia: "En curso"},
    {Desde: "En espera del solicitante", Hacia: "Resuelto"},
    {Desde: "En espera del solicitante", Hacia: "Cancelado"},
    {Desde: "Reabierto", Hacia: "En curso"},
    {Desde: "Reabierto", Hacia: "En espera del solicitante"},
    {Desde: "Reabierto", Hacia: "Resuelto"},
    {Desde: "Reabierto", Hacia: "Cancelado"}
);
SubestadosPorEstado = Table(
    {Estado: "Nuevo", Subestado: "Sin clasificar"},
    {Estado: "Asignado", Subestado: "En cola del analista"},
    {Estado: "En curso", Subestado: "En análisis"},
    {Estado: "En curso", Subestado: "En desarrollo"},
    {Estado: "En curso", Subestado: "Esperando a IT / fuente de datos"},
    {Estado: "En curso", Subestado: "En validación de datos"},
    {Estado: "En curso", Subestado: "En aprobación"},
    {Estado: "En espera del solicitante", Subestado: "Esperando información"},
    {Estado: "En espera del solicitante", Subestado: "Esperando aprobación del solicitante"},
    {Estado: "En espera del solicitante", Subestado: "Esperando validación"},
    {Estado: "Resuelto", Subestado: "Esperando conformidad"},
    {Estado: "Reabierto", Subestado: "No conforme"},
    {Estado: "Cerrado", Subestado: "Conforme"},
    {Estado: "Cerrado", Subestado: "Conformidad tácita"},
    {Estado: "Cancelado", Subestado: "Duplicado"},
    {Estado: "Cancelado", Subestado: "Fuera de alcance"},
    {Estado: "Cancelado", Subestado: "Lo retiró el solicitante"}
);
ColoresEstado = Table(
    {Estado: "Nuevo", Fondo: "#3B4A5E", Letra: "#FFFFFF"},
    {Estado: "Asignado", Fondo: "#627082", Letra: "#FFFFFF"},
    {Estado: "En curso", Fondo: "#FAB005", Letra: "#3B4A5E"},
    {Estado: "En espera del solicitante", Fondo: "#FAB005", Letra: "#3B4A5E"},
    {Estado: "Resuelto", Fondo: "#0D8460", Letra: "#FFFFFF"},
    {Estado: "Reabierto", Fondo: "#EB002C", Letra: "#FFFFFF"},
    {Estado: "Cerrado", Fondo: "#E3E8F0", Letra: "#3B4A5E"},
    {Estado: "Cancelado", Fondo: "#E3E8F0", Letra: "#3B4A5E"}
);
Equipos = ["Excelencia Comercial", "Digital"];
UnidadesNegocio = ["Cardiovascular", "Gastro + Hipercol.", "Metab & Obesidad Lic", "Metab & Obesidad Pr", "Neurociencias", "Osteo Dolor", "Salud de la Mujer", "Salud del Hombre", "Oncología", "Otra", "Transversal / no aplica"];
AreasTerapeuticas = ["Metab & Obesidad", "Cardiovascular", "Aparato Digestivo", "Neurociencias", "Osteo Dolor", "Salud de la Mujer", "Salud del Hombre", "Oncología", "Otra", "Transversal / no aplica"];
HoraFin = 18;
DiasTacita = 3;
