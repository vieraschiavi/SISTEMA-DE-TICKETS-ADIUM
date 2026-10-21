-- Tickets · Excelencia Comercial & Digital — esquema para SQL Server.
-- Es el mismo de tickets_ec/almacen.py (SQLite). Se genera, no se aplica:
-- lo corre un DBA en la base que elija IT (p. ej. BI_JC_Analisis en 10.1.3.60).
-- Las vistas vw_* son lo que puede leer Power BI en lugar del Excel.

CREATE SCHEMA tickets AUTHORIZATION dbo;
GO

CREATE TABLE tickets.personas (
    mail        NVARCHAR(320) NOT NULL PRIMARY KEY,
    nombre      NVARCHAR(200) NOT NULL,
    area        NVARCHAR(100) NULL,
    pais        NVARCHAR(60)  NULL,
    rol         NVARCHAR(20)  NOT NULL DEFAULT 'solicitante',
    activo      BIT NOT NULL DEFAULT 1
);

CREATE TABLE tickets.tickets (
    id                    INT IDENTITY(1,1) PRIMARY KEY,
    numero                AS ('EC-' + RIGHT('00000' + CAST(id AS VARCHAR(10)), 5)) PERSISTED,
    asunto                NVARCHAR(250) NOT NULL,
    descripcion           NVARCHAR(MAX) NULL,
    solicitante_mail      NVARCHAR(320) NOT NULL,
    solicitante_nombre    NVARCHAR(200) NULL,
    area                  NVARCHAR(100) NULL,
    pais                  NVARCHAR(60)  NULL,
    tipo                  NVARCHAR(60)  NULL,
    subtipo               NVARCHAR(80)  NULL,
    atc                   NVARCHAR(10)  NULL,
    area_terapeutica      NVARCHAR(60)  NULL,
    unidad_negocio        NVARCHAR(60)  NULL,
    mercado               NVARCHAR(120) NULL,
    fuente_datos          NVARCHAR(60)  NULL,
    tablero               NVARCHAR(200) NULL,
    prioridad             NVARCHAR(20)  NULL,
    canal                 NVARCHAR(20)  NULL,
    estado                NVARCHAR(40)  NOT NULL,
    subestado             NVARCHAR(60)  NULL,
    equipo                NVARCHAR(40)  NULL,
    analista_mail         NVARCHAR(320) NULL,
    cc                    NVARCHAR(1000) NULL,
    clasificacion         NVARCHAR(1000) NULL,
    message_id            NVARCHAR(500) NULL,
    creado_en             DATETIME2(0) NOT NULL,
    actualizado_en        DATETIME2(0) NOT NULL,
    asignado_en           DATETIME2(0) NULL,
    primera_respuesta_en  DATETIME2(0) NULL,
    en_curso_en           DATETIME2(0) NULL,
    resuelto_en           DATETIME2(0) NULL,
    cerrado_en            DATETIME2(0) NULL,
    cancelado_en          DATETIME2(0) NULL,
    reaperturas           INT NOT NULL DEFAULT 0,
    veces_en_espera       INT NOT NULL DEFAULT 0,
    conformidad           NVARCHAR(20) NOT NULL DEFAULT 'Sin encuesta',
    csat                  TINYINT NULL CHECK (csat BETWEEN 1 AND 5),
    resolucion            NVARCHAR(MAX) NULL
);
CREATE INDEX ix_tickets_estado ON tickets.tickets(estado) INCLUDE (equipo, analista_mail);
CREATE UNIQUE INDEX ux_tickets_numero ON tickets.tickets(numero);

CREATE TABLE tickets.eventos (
    id            BIGINT IDENTITY(1,1) PRIMARY KEY,
    ticket_id     INT NOT NULL REFERENCES tickets.tickets(id),
    en            DATETIME2(0) NOT NULL,
    usuario       NVARCHAR(320) NOT NULL,
    tipo          NVARCHAR(30) NOT NULL,
    estado_desde  NVARCHAR(40) NULL,
    estado_hasta  NVARCHAR(40) NULL,
    publico       BIT NOT NULL DEFAULT 0,
    detalle       NVARCHAR(MAX) NULL
);
CREATE INDEX ix_eventos_ticket ON tickets.eventos(ticket_id, en);

CREATE TABLE tickets.encuestas (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    ticket_id     INT NOT NULL REFERENCES tickets.tickets(id),
    ronda         INT NOT NULL,
    token_hash    CHAR(64) NOT NULL UNIQUE,
    enviada_en    DATETIME2(0) NOT NULL,
    respondida_en DATETIME2(0) NULL,
    resultado     NVARCHAR(20) NOT NULL DEFAULT 'Pendiente',
    csat          TINYINT NULL,
    comentario    NVARCHAR(MAX) NULL
);

CREATE TABLE tickets.correos (
    message_id    NVARCHAR(500) NOT NULL PRIMARY KEY,
    ticket_id     INT NULL REFERENCES tickets.tickets(id),
    recibido_en   DATETIME2(0) NOT NULL,
    remitente     NVARCHAR(320) NULL,
    asunto        NVARCHAR(500) NULL,
    resultado     NVARCHAR(200) NOT NULL
);
GO

-- Las horas hábiles con el reloj detenido NO se calculan en SQL: las calcula
-- scripts/exportar_powerbi.py con el mismo código que la bandeja. Estas vistas
-- dan la parte que sí es SQL simple, para consultas ad hoc.
CREATE VIEW tickets.vw_tickets_mensual AS
SELECT FORMAT(creado_en, 'yyyy-MM') AS periodo, equipo, tipo, area, pais, unidad_negocio, area_terapeutica,
       COUNT(*) AS recibidos,
       SUM(CASE WHEN resuelto_en IS NOT NULL THEN 1 ELSE 0 END) AS resueltos,
       SUM(CASE WHEN estado IN ('Nuevo', 'Asignado', 'En curso', 'Reabierto') THEN 1 ELSE 0 END) AS pendientes,
       SUM(CASE WHEN conformidad = 'Conforme' THEN 1 ELSE 0 END) AS conformes,
       SUM(CASE WHEN conformidad = 'No conforme' THEN 1 ELSE 0 END) AS no_conformes,
       AVG(CAST(csat AS DECIMAL(4, 2))) AS csat_promedio
FROM tickets.tickets WITH (NOLOCK)
GROUP BY FORMAT(creado_en, 'yyyy-MM'), equipo, tipo, area, pais, unidad_negocio, area_terapeutica;
GO
