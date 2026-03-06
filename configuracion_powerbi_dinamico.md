# 📊 CONFIGURACIÓN POWER BI DINÁMICO PARA TUCLIMA IA

## 🎯 OBJETIVO
Permitir que la IA genere gráficos dinámicos basados en peticiones de usuarios

## 📋 REPORTES BASE A CREAR EN POWER BI

### 1. **REPORTE MASTER** (Página Principal)
- **Nombre**: `TuClima_Master_Dynamic`
- **URL Embed**: Será la URL que ya tienes configurada
- **Filtros Dinámicos**:
  - Parámetro `sector` (agro, naval, aereo, energia)
  - Parámetro `ubicacion` (lat, lon o ciudad)
  - Parámetro `fecha_inicio` y `fecha_fin`
  - Parámetro `tipo_analisis` (valor_principal, valor_secundario)

### 2. **TEMPLATES DE VISUALIZACIÓN**

#### Template A: **Línea de Tiempo**
```dax
// Medida para valor dinámico
Valor_Dinamico = 
    SWITCH(
        SELECTEDVALUE('Parametros'[TipoValor]),
        "principal", SUM('DatosClima'[valor_principal]),
        "secundario", SUM('DatosClima'[valor_secundario]),
        "temperatura", AVERAGE('DatosClima'[temperatura]),
        "humedad", AVERAGE('DatosClima'[humedad]),
        "viento", AVERAGE('DatosClima'[viento]),
        SUM('DatosClima'[valor_principal])
    )
```

#### Template B: **Mapa Geográfico**
```dax
// Medida para intensidad del mapa
Intensidad_Mapa = 
    SWITCH(
        SELECTEDVALUE('Parametros'[MetricaMapa]),
        "riesgo", [Valor_Riesgo_Calculado],
        "temperatura", [Valor_Dinamico],
        "precipitacion", SUM('DatosClima'[precipitacion]),
        [Valor_Dinamico]
    )
```

#### Template C: **Comparativa Sectorial**
```dax
// Comparación entre sectores
Comparativa_Sectores = 
    CALCULATE(
        [Valor_Dinamico],
        FILTER(
            'DatosClima',
            'DatosClima'[sector] = SELECTEDVALUE('Parametros'[SectorComparacion])
        )
    )
```

#### Template D: **Análisis Predictivo**
```dax
// Predicción basada en IA
Prediccion_IA = 
    VAR AnalisisIA = SELECTEDVALUE('DatosClima'[analisis_ia])
    VAR ValorActual = [Valor_Dinamico]
    RETURN
        IF(
            AnalisisIA = "ALTO_RIESGO", ValorActual * 1.3,
            IF(AnalisisIA = "RIESGO_MEDIO", ValorActual * 1.1,
            IF(AnalisisIA = "BAJO_RIESGO", ValorActual * 0.9,
            ValorActual))
        )
```

## 🔗 CONFIGURACIÓN URL EMBEDDING

### URLs Base para Diferentes Tipos de Gráfico:

1. **Gráfico de Líneas**:
   ```
   https://app.powerbi.com/view?r=TU_REPORT_ID&filter=DatosClima/sector eq 'SECTOR'&filter=DatosClima/ubicacion eq 'UBICACION'&pageView=fitToWidth
   ```

2. **Mapa de Calor**:
   ```
   https://app.powerbi.com/view?r=TU_REPORT_ID&filter=DatosClima/fecha_registro ge datetime'2024-01-01'&pageView=actualSize
   ```

3. **Comparativa**:
   ```
   https://app.powerbi.com/view?r=TU_REPORT_ID&filter=Parametros/TipoAnalisis eq 'comparativa'&pageView=fitToWidth
   ```

## 🎛️ PARÁMETROS REQUERIDOS EN POWER BI

### Tabla de Parámetros a crear:
```
Tabla: Parametros
Campos:
- TipoGrafico: "lineal", "barras", "mapa", "comparativa", "predictivo"
- TipoValor: "principal", "secundario", "temperatura", "humedad", "viento"
- SectorActivo: "agro", "naval", "aereo", "energia", "todos"
- RangoTiempo: "24h", "7d", "30d", "custom"
- MetricaMapa: "riesgo", "temperatura", "precipitacion"
- SectorComparacion: sector a comparar
```

## 🌐 PÁGINAS DEL REPORTE

### Página 1: **Dashboard General**
- KPIs principales por sector
- Mapa general con últimas alertas
- Gráfico de tendencias últimos 7 días

### Página 2: **Análisis Temporal**
- Gráfico de líneas configurable
- Filtros de fecha dinámicos
- Comparativa vs histórico

### Página 3: **Mapa Geográfico**
- Mapa de intensidades
- Capas configurables
- Drill-down por ubicación

### Página 4: **Comparativa Sectorial**
- Gráficos de barras comparativo
- Análisis de correlación
- Rankings por sector

### Página 5: **Predictivo/IA**
- Tendencias pronosticadas
- Análisis de IA
- Alertas tempranas

## ⚙️ CONFIGURACIÓN DE FILTROS

### Segmentadores (Slicers) Requeridos:
1. **Sector** - Lista desplegable
2. **Ubicación** - Mapa o lista
3. **Rango de Fechas** - Date picker
4. **Tipo de Métrica** - Lista de métricas disponibles
5. **Nivel de Detalle** - Horario/Diario/Semanal

## 🔧 CONFIGURACIÓN TÉCNICA

### 1. Conexión BigQuery:
- Configurar refresh automático cada 15 minutos
- Query incremental para optimización
- Parámetros de filtrado a nivel de query

### 2. Performance:
- Agregaciones pre-calculadas
- Índices en campos de filtro
- Caché de consultas frecuentes

### 3. Seguridad:
- Row Level Security por región/sector si es necesario
- Tokens de acceso con expiración

## 📱 RESPONSIVE DESIGN

### Configuración para móviles:
- Vista mobile optimizada
- Gráficos adaptables
- Controles touch-friendly

---

## 🚀 SIGUIENTE PASO
Una vez creados estos reportes base, configuraremos N8N para generar las URLs dinámicas específicas.