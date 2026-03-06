# 📊 CONFIGURACIÓN SCHEMA BIGQUERY PARA WORKFLOWS N8N

## Estructura de Tablas Requeridas

### Tabla Principal: workflow_responses
```sql
CREATE TABLE `proyecto-bi-488218.datos_clima.workflow_responses` (
  timestamp TIMESTAMP,
  session_id STRING,
  sector STRING,
  chat_input STRING,
  ai_response STRING,
  location STRING,
  metadata JSON,
  -- Campos específicos por sector
  naval_data JSON,
  agro_data JSON,
  aereo_data JSON,
  energia_data JSON
);
```

### Tablas Específicas por Sector

#### Naval
```sql
CREATE TABLE `proyecto-bi-488218.datos_clima.naval` (
  timestamp TIMESTAMP,
  session_id STRING,
  puerto STRING,
  condiciones_mar STRING,
  viento_velocidad FLOAT64,
  viento_direccion STRING,
  temperatura_agua FLOAT64,
  altura_olas FLOAT64,
  visibilidad STRING,
  ai_analysis STRING,
  metadata JSON
);
```

#### Agro
```sql
CREATE TABLE `proyecto-bi-488218.datos_clima.agro` (
  timestamp TIMESTAMP,
  session_id STRING,
  cultivo STRING,
  region STRING,
  temperatura_suelo FLOAT64,
  humedad_relativa FLOAT64,
  precipitacion FLOAT64,
  horas_sol FLOAT64,
  fase_lunar STRING,
  ai_recommendations STRING,
  metadata JSON
);
```

#### Aereo
```sql
CREATE TABLE `proyecto-bi-488218.datos_clima.aereo` (
  timestamp TIMESTAMP,
  session_id STRING,
  aeropuerto_origen STRING,
  aeropuerto_destino STRING,
  altitud_vuelo FLOAT64,
  temperatura_altitud FLOAT64,
  corrientes_viento JSON,
  visibilidad_km FLOAT64,
  condiciones_atmosfericas STRING,
  ai_flight_analysis STRING,
  metadata JSON
);
```

#### Energia
```sql
CREATE TABLE `proyecto-bi-488218.datos_clima.energia` (
  timestamp TIMESTAMP,
  session_id STRING,
  tipo_energia STRING, -- solar, eolica, hidro
  ubicacion STRING,
  radiacion_solar FLOAT64,
  velocidad_viento FLOAT64,
  temperatura_ambiente FLOAT64,
  eficiencia_estimada FLOAT64,
  produccion_kwh FLOAT64,
  ai_efficiency_analysis STRING,
  metadata JSON
);
```