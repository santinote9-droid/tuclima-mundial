-- ============================================================
-- FASE 2 · ESTADÍSTICA CLIMÁTICA — Histórico real (n8n + BigQuery)
-- Ejecutar UNA sola vez en el proyecto BigQuery ya usado por n8n
-- (proyecto-bi-488218, dataset datos_clima) antes de activar el
-- workflow "Snapshot Histórico Clima".
-- ============================================================

CREATE TABLE IF NOT EXISTS `proyecto-bi-488218.datos_clima.snapshots_historicos`
(
  timestamp         TIMESTAMP   NOT NULL,   -- momento del snapshot (UTC)
  sector            STRING      NOT NULL,   -- agro | naval | aereo | energia
  lat               FLOAT64     NOT NULL,
  lon               FLOAT64     NOT NULL,
  nombre_ubicacion  STRING,                 -- nombre guardado por el usuario (o "Default")
  variable          STRING      NOT NULL,   -- ej: "temperatura", "precipitacion", "olas"...
  valor             FLOAT64     NOT NULL
)
PARTITION BY DATE(timestamp)
CLUSTER BY sector, variable;

-- Notas:
-- * Formato "largo" (una fila por variable) para no tener que alterar el
--   esquema cada vez que se agregue una variable nueva a un sector.
-- * Particionado por día + clustering por sector/variable: las consultas
--   de "hoy vs. promedio de semanas pasadas" (que siempre filtran por
--   sector + variable + rango de fechas) van a leer mucho menos escaneo/costo.
-- * El join "misma lat/lon" en las consultas usa tolerancia de ±0.05°
--   (~5 km) para tolerar pequeñas diferencias de redondeo entre corridas.
