# 📊 CONFIGURACIÓN POWER BI → BIGQUERY

## 🔗 Conectar Power BI con BigQuery

### Paso 1: Instalar Conector BigQuery
1. Abrir Power BI Desktop
2. Ir a **Datos** → **Obtener datos**
3. Buscar "Google BigQuery"
4. Hacer clic **Conectar**

### Paso 2: Autenticación
1. Usar cuenta de Google del proyecto: `proyecto-bi-488218`
2. Autorizar acceso a BigQuery
3. Seleccionar proyecto: **proyecto-bi-488218**

### Paso 3: Seleccionar Datos

#### Tablas Principales para Dashboards:
- `proyecto-bi-488218.datos_clima.workflow_responses` (Datos generales)
- `proyecto-bi-488218.datos_clima.naval` (Sector Naval)
- `proyecto-bi-488218.datos_clima.agro` (Sector Agrícola)
- `proyecto-bi-488218.datos_clima.aereo` (Sector Aéreo)
- `proyecto-bi-488218.datos_clima.energia` (Sector Energético)

### Paso 4: Queries DirectQuery Recomendadas

#### Query 1: Resumen por Sectores
```sql
SELECT 
  sector,
  COUNT(*) as total_consultas,
  DATE(timestamp) as fecha,
  EXTRACT(HOUR FROM timestamp) as hora
FROM `proyecto-bi-488218.datos_clima.workflow_responses`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY sector, fecha, hora
ORDER BY fecha DESC, hora DESC
```

#### Query 2: Tendencias Naval
```sql
SELECT 
  DATE(timestamp) as fecha,
  puerto,
  AVG(viento_velocidad) as viento_promedio,
  AVG(temperatura_agua) as temp_agua_promedio,
  AVG(altura_olas) as olas_promedio,
  COUNT(*) as num_consultas
FROM `proyecto-bi-488218.datos_clima.naval`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY fecha, puerto
ORDER BY fecha DESC
```

#### Query 3: Análisis Energético
```sql
SELECT 
  DATE(timestamp) as fecha,
  tipo_energia,
  ubicacion,
  AVG(radiacion_solar) as radiacion_promedio,
  AVG(velocidad_viento) as viento_promedio,
  AVG(eficiencia_estimada) as eficiencia_promedio,
  SUM(produccion_kwh) as produccion_total
FROM `proyecto-bi-488218.datos_clima.energia`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
  AND tipo_energia IS NOT NULL
GROUP BY fecha, tipo_energia, ubicacion
ORDER BY fecha DESC
```

#### Query 4: Dashboard Agro
```sql
SELECT 
  DATE(timestamp) as fecha,
  cultivo,
  region,
  AVG(temperatura_suelo) as temp_suelo_promedio,
  AVG(humedad_relativa) as humedad_promedio,
  AVG(precipitacion) as lluvia_promedio,
  AVG(horas_sol) as sol_promedio
FROM `proyecto-bi-488218.datos_clima.agro`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND cultivo IS NOT NULL
GROUP BY fecha, cultivo, region
ORDER BY fecha DESC
```

### Paso 5: Configurar Actualización Automática

#### En Power BI Service:
1. Publicar reporte en workspace
2. Ir a **Conjuntos de datos**
3. Configurar **Actualización programada**
4. Établecer frecuencia: **Cada hora** (recomendado)

#### Credenciales Gateway:
- Usar **DirectQuery** para datos en tiempo real
- O **Import mode** con actualización cada 15 minutos

## 📈 Dashboards Recomendados

### Dashboard 1: Overview General
- **Gráfico de barras**: Consultas por sector (últimos 7 días)
- **Gráfico de líneas**: Tendencia de uso por horas
- **Mapa**: Ubicaciones más consultadas
- **KPIs**: Total consultas, sectores activos, tiempo promedio respuesta

### Dashboard 2: Sector Naval
- **Gráfico de ondas**: Altura de olas por puerto
- **Rosa de vientos**: Dirección y velocidad del viento
- **Tabla**: Condiciones actuales por puerto
- **Mapa de calor**: Temperatura del agua

### Dashboard 3: Sector Energético  
- **Gráfico de área**: Producción solar vs eólica
- **Gauge**: Eficiencia actual vs objetivo
- **Matriz**: Producción por ubicación y tipo
- **Líneas**: Tendencias de radiación solar

### Dashboard 4: Sector Agrícola
- **Calendario**: Condiciones por día del mes
- **Comparativo**: Humedad vs precipitación
- **Segmentación**: Por tipo de cultivo
- **Alertas**: Condiciones adversas

### Dashboard 5: Sector Aéreo
- **Rutas**: Mapa de vuelos analizados
- **Altitud vs Temperatura**: Gráfico dispersión
- **Timeline**: Condiciones de vuelo por hora
- **Alertas**: Condiciones meteorológicas adversas

## 🔧 Configuración Avanzada

### Medidas Calculadas DAX:

#### Última Actualización
```dax
Ultima_Actualizacion = 
MAX(workflow_responses[timestamp])
```

#### Consultas por Hora
```dax
Consultas_Ultima_Hora = 
CALCULATE(
    COUNT(workflow_responses[session_id]),
    workflow_responses[timestamp] >= NOW() - 1/24
)
```

#### Eficiencia Promedio Energía
```dax
Eficiencia_Promedio = 
AVERAGE(energia[eficiencia_estimada])
```

### Parámetros What-If:
- **Rango de fechas**: Para análisis históricos
- **Umbral de alertas**: Para notificaciones automáticas
- **Filtro de ubicación**: Para análisis geográfico