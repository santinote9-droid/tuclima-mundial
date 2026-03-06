# 🎨 GUÍA PASO A PASO - CONFIGURACIÓN POWER BI DESKTOP

## 🚀 CONFIGURACIÓN DATOS Y MODELO

### 1. **CONEXIÓN A BIGQUERY** (Ya configurada)
✅ Tienes conectado BigQuery con las siguientes tablas específicas por sector:

#### **NAVAL_BI** (Sector Naval):
- `timestamp`, `session_id`, `puerto`, `condiciones_mar`
- `viento_velocidad`, `viento_direccion`, `temperatura_agua`
- `altura_olas`, `visibilidad`, `ai_analysis`, `metadata`

#### **AGRO_BI** (Sector Agrícola):
- `timestamp`, `session_id`, `cultivo`, `region`
- `temperatura_suelo`, `humedad_relativa`, `precipitacion` 
- `horas_sol`, `fase_lunar`, `ai_recommendations`, `metadata`

#### **AEREO_BI** (Sector Aéreo):
- `timestamp`, `session_id`, `aeropuerto_origen`, `aeropuerto_destino`
- `altitud_vuelo`, `temperatura_altitud`, `corrientes_viento`
- `visibilidad_km`, `condiciones_atmosfericas`, `ai_flight_analysis`, `metadata`

#### **ENERGIA_BI** (Sector Energético):
- `timestamp`, `session_id`, `tipo_energia`, `ubicacion`
- `radiacion_solar`, `velocidad_viento`, `temperatura_ambiente`
- `eficiencia_estimada`, `produccion_kwh`, `ai_efficiency_analysis`, `metadata`

### 2. **CREAR TABLA DE SELECTOR DE SECTOR**

En Power Query Editor:
```M
// Crear tabla SelectorSector
let
    Source = Table.FromRows({
        {"naval", "Naval", "NAVAL_BI", "#06B6D4"},
        {"agro", "Agricultura", "AGRO_BI", "#10B981"},
        {"aereo", "Aviación", "AEREO_BI", "#F59E0B"},
        {"energia", "Energía", "ENERGIA_BI", "#EF4444"}
    }, {"SectorID", "SectorNombre", "TablaBD", "Color"}),
    #"Changed Type" = Table.TransformColumnTypes(Source,{
        {"SectorID", type text}, 
        {"SectorNombre", type text}, 
        {"TablaBD", type text},
        {"Color", type text}
    })
in
    #"Changed Type"
```

### 3. **CREAR TABLA DE MÉTRICAS POR SECTOR**

```M
// Crear tabla MetricasPorSector 
let
    Source = Table.FromRows({
        {"naval", "viento_velocidad", "Velocidad Viento", "nudos"},
        {"naval", "altura_olas", "Altura Olas", "metros"},
        {"naval", "temperatura_agua", "Temperatura Agua", "°C"},
        {"naval", "visibilidad", "Visibilidad", "km"},
        
        {"agro", "humedad_relativa", "Humedad Relativa", "%"},
        {"agro", "temperatura_suelo", "Temperatura Suelo", "°C"},
        {"agro", "precipitacion", "Precipitación", "mm"},
        {"agro", "horas_sol", "Horas de Sol", "hs"},
        
        {"aereo", "temperatura_altitud", "Temperatura Altitud", "°C"},
        {"aereo", "visibilidad_km", "Visibilidad", "km"},
        {"aereo", "altitud_vuelo", "Altitud de Vuelo", "pies"},
        
        {"energia", "eficiencia_estimada", "Eficiencia", "%"},
        {"energia", "radiacion_solar", "Radiación Solar", "W/m2"},
        {"energia", "produccion_kwh", "Producción", "kWh"},
        {"energia", "velocidad_viento", "Velocidad Viento", "km/h"}
    }, {"Sector", "CampoID", "NombreMetrica", "Unidad"}),
    #"Changed Type" = Table.TransformColumnTypes(Source,{
        {"Sector", type text}, 
        {"CampoID", type text}, 
        {"NombreMetrica", type text},
        {"Unidad", type text}
    })
in
    #"Changed Type"
```

---

## 📊 MEDIDAS DAX PRINCIPALES

### 1. **Valor Naval Dinámico**
```dax
Valor_Naval = 
SWITCH(
    TRUE(),
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "viento_velocidad",
        AVERAGE('NAVAL_BI'[viento_velocidad]),
    
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "altura_olas", 
        AVERAGE('NAVAL_BI'[altura_olas]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "temperatura_agua",
        AVERAGE('NAVAL_BI'[temperatura_agua]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "visibilidad",
        AVERAGE('NAVAL_BI'[visibilidad]),
        
    // Por defecto: viento_velocidad
    AVERAGE('NAVAL_BI'[viento_velocidad])
)
```

### 2. **Valor Agrícola Dinámico**
```dax
Valor_Agro = 
SWITCH(
    TRUE(),
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "humedad_relativa",
        AVERAGE('AGRO_BI'[humedad_relativa]),
    
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "temperatura_suelo", 
        AVERAGE('AGRO_BI'[temperatura_suelo]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "precipitacion",
        SUM('AGRO_BI'[precipitacion]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "horas_sol",
        AVERAGE('AGRO_BI'[horas_sol]),
        
    // Por defecto: humedad_relativa
    AVERAGE('AGRO_BI'[humedad_relativa])
)
```

### 3. **Valor Aéreo Dinámico**
```dax
Valor_Aereo = 
SWITCH(
    TRUE(),
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "temperatura_altitud",
        AVERAGE('AEREO_BI'[temperatura_altitud]),
    
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "visibilidad_km", 
        AVERAGE('AEREO_BI'[visibilidad_km]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "altitud_vuelo",
        AVERAGE('AEREO_BI'[altitud_vuelo]),
        
    // Por defecto: temperatura_altitud
    AVERAGE('AEREO_BI'[temperatura_altitud])
)
```

### 4. **Valor Energético Dinámico**
```dax
Valor_Energia = 
SWITCH(
    TRUE(),
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "eficiencia_estimada",
        AVERAGE('ENERGIA_BI'[eficiencia_estimada]),
    
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "radiacion_solar", 
        AVERAGE('ENERGIA_BI'[radiacion_solar]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "produccion_kwh",
        SUM('ENERGIA_BI'[produccion_kwh]),
        
    ISFILTERED('Metricas'[MetricaID]) && SELECTEDVALUE('Metricas'[MetricaID]) = "velocidad_viento",
        AVERAGE('ENERGIA_BI'[velocidad_viento]),
        
    // Por defecto: eficiencia_estimada
    AVERAGE('ENERGIA_BI'[eficiencia_estimada])
)
```

### 5. **Medida Unificada por Sector**
```dax
Valor_Actual = 
VAR SectorActual = SELECTEDVALUE('SectorSelector'[Sector], "naval")
RETURN
    SWITCH(
        SectorActual,
        "naval", [Valor_Naval],
        "agro", [Valor_Agro],
        "aereo", [Valor_Aereo],
        "energia", [Valor_Energia],
        [Valor_Naval] // Por defecto
    )
```

### 6. **Análisis IA por Sector**
```dax
Analisis_IA = 
VAR SectorActual = SELECTEDVALUE('SectorSelector'[Sector], "naval")
RETURN
    SWITCH(
        SectorActual,
        "naval", SELECTEDVALUE('NAVAL_BI'[ai_analysis]),
        "agro", SELECTEDVALUE('AGRO_BI'[ai_recommendations]),
        "aereo", SELECTEDVALUE('AEREO_BI'[ai_flight_analysis]),
        "energia", SELECTEDVALUE('ENERGIA_BI'[ai_efficiency_analysis]),
        ""
    )
```

### 7. **Color por Análisis IA**
```dax
Color_Analisis = 
VAR AnalisisTexto = [Analisis_IA]
RETURN
    SWITCH(
        TRUE(),
        CONTAINSSTRING(AnalisisTexto, "ALTO") || CONTAINSSTRING(AnalisisTexto, "CRITICO"), "#FF4444",
        CONTAINSSTRING(AnalisisTexto, "MEDIO") || CONTAINSSTRING(AnalisisTexto, "MODERADO"), "#FF8800", 
        CONTAINSSTRING(AnalisisTexto, "BAJO") || CONTAINSSTRING(AnalisisTexto, "OPTIMO"), "#44AA44",
        "#0088CC"
    )
```

---

## 📄 CONFIGURACIÓN DE PÁGINAS

### **PÁGINA 1: Dashboard Sectorial** 
**Nombre**: `ReportSection_Dashboard`

#### Visuales requeridos:

1. **Slicer de Sector** (Superior izquierda):
   - Campo: `'SelectorSector'[SectorNombre]`
   - Estilo: Buttons
   - Single select

2. **KPI Naval** (Cuando sector = Naval):
   - Valor: `[Valor_Naval]`
   - Título: `"Naval - " & SELECTEDVALUE('MetricasPorSector'[NombreMetrica], "Viento")`
   - Filtro de página: `SelectorSector[SectorID] = "naval"`

3. **KPI Agrícola** (Cuando sector = Agro):
   - Valor: `[Valor_Agro]`
   - Título: `"Agricultura - " & SELECTEDVALUE('MetricasPorSector'[NombreMetrica], "Humedad")`
   - Filtro de página: `SelectorSector[SectorID] = "agro"`

4. **KPI Aéreo** (Cuando sector = Aéreo):
   - Valor: `[Valor_Aereo]` 
   - Título: `"Aviación - " & SELECTEDVALUE('MetricasPorSector'[NombreMetrica], "Temperatura")`
   - Filtro de página: `SelectorSector[SectorID] = "aereo"`

5. **KPI Energético** (Cuando sector = Energía):
   - Valor: `[Valor_Energia]`
   - Título: `"Energía - " & SELECTEDVALUE('MetricasPorSector'[NombreMetrica], "Eficiencia")`
   - Filtro de página: `SelectorSector[SectorID] = "energia"`

6. **Gráfico de Barras** - Comparativa por Hora:
   - Eje X: `timestamp` (hora)
   - Eje Y: `[Valor_Actual]` 
   - Legend: ANÁLISIS IA
   - Colores: `[Color_Analisis]`

### **PÁGINA 2: Análisis Temporal Naval**
**Nombre**: `ReportSection_Naval_Temporal`

1. **Gráfico de Líneas Principal**:
   - Eje X: `'NAVAL_BI'[timestamp]`
   - Eje Y: `[Valor_Naval]`
   - Legend: `'NAVAL_BI'[puerto]`
   - Filtro automático: Solo tabla NAVAL_BI

2. **Tabla de Detalles Naval**:
   - Campos: timestamp, puerto, viento_velocidad, altura_olas, ai_analysis

### **PÁGINA 3: Análisis Temporal Agro**
**Nombre**: `ReportSection_Agro_Temporal`

1. **Gráfico de Líneas Principal**:
   - Eje X: `'AGRO_BI'[timestamp]`
   - Eje Y: `[Valor_Agro]`
   - Legend: `'AGRO_BI'[cultivo]`

2. **Tabla de Detalles Agro**:
   - Campos: timestamp, cultivo, region, humedad_relativa, temperatura_suelo, ai_recommendations

### **PÁGINA 4: Análisis Temporal Aereo**
**Nombre**: `ReportSection_Aereo_Temporal`

1. **Gráfico de Líneas Principal**:
   - Eje X: `'AEREO_BI'[timestamp]`
   - Eje Y: `[Valor_Aereo]`
   - Legend: Ruta (origen + destino)

### **PÁGINA 5: Análisis Temporal Energia**
**Nombre**: `ReportSection_Energia_Temporal`

1. **Gráfico de Líneas Principal**:
   - Eje X: `'ENERGIA_BI'[timestamp]`
   - Eje Y: `[Valor_Energia]`
   - Legend: `'ENERGIA_BI'[tipo_energia]`

---

## 🎛️ FILTROS Y SEGMENTADORES

### Filtros globales (en cada página):

1. **Slicer de Sector**:
   - Campo: `'DatosClima'[sector]`
   - Estilo: Dropdown
   - Sync: Todas las páginas

2. **Date Range Picker**:
   - Campo: `'DatosClima'[fecha_registro]`
   - Tipo: Between
   - Default: Últimos 7 días

3. **Slicer de Métrica** (solo en páginas apropiadas):
   - Campo: `'Metricas'[MetricaID]`  
   - Estilo: Buttons
   - Single select

---

## 🎨 FORMATO Y TEMA

### Configuración de Tema:
```json
{
  "name": "TuClima Dark",
  "dataColors": [
    "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
    "#3B82F6", "#F97316", "#84CC16", "#EC4899", "#6366F1"
  ],
  "background": "#0F172A",
  "foreground": "#F8FAFC",
  "tableAccent": "#1E293B"
}
```

### Configuraciones específicas:
- **Título de página**: Fuente Segoe UI, 18pt, Color #06B6D4
- **Fondos**: Transparentes o #1E293B con 80% opacity
- **Bordes**: #334155, 1px
- **Tooltips**: Background #0F172A, texto #F8FAFC

---

## 🔗 CONFIGURACIÓN DE URL PARAMETERS

### En Power BI Service (después de publicar):

1. **Configurar URL filtering**:
   - Habilitar en Settings > Parameters
   - Permitir filtering por URL

2. **Test URLs**:
```
// Dashboard general
https://app.powerbi.com/view?r=TU_REPORT_ID&pageName=ReportSection_Dashboard

// Filtro por sector
https://app.powerbi.com/view?r=TU_REPORT_ID&filter=DatosClima/sector eq 'naval'

// Filtro temporal  
https://app.powerbi.com/view?r=TU_REPORT_ID&filter=DatosClima/fecha_registro ge datetime'2026-02-20'
```

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

### ✅ Preparación:
- [ ] Datos de BigQuery conectados
- [ ] Tablas Parametros y Metricas creadas
- [ ] Medidas DAX implementadas

### 📊 Páginas:
- [ ] Dashboard General completada
- [ ] Análisis Temporal completado
- [ ] Mapa Geográfico completado
- [ ] Comparativa Sectorial completada
- [ ] Modelo Predictivo completado

### 🎛️ Configuración:
- [ ] Filtros sincronizados
- [ ] Tema aplicado
- [ ] URLs de test funcionando
- [ ] Performance optimizada

### 🚀 Deploy:
- [ ] Publicado en Power BI Service
- [ ] URLs embedding configuradas
- [ ] Permisos configurados
- [ ] Refresh schedule configurado

---

## 🔧 TROUBLESHOOTING COMÚN

### Error: "Cannot parse ubicacion field"
**Solución**: Crear columnas calculadas para lat/lon:
```dax
Latitud = TRIM(LEFT(SUBSTITUTE('DatosClima'[ubicacion], ",", " "), 10))
Longitud = TRIM(RIGHT(SUBSTITUTE('DatosClima'[ubicacion], ",", " "), 10))
```

### Error: "Slow performance on large datasets"  
**Solución**: 
1. Crear agregaciones en BigQuery
2. Usar DirectQuery mode
3. Implementar incremental refresh

### Error: "URL filters not working"
**Solución**:
1. Verificar nombres exactos de tablas/campos
2. URL encoding correcto
3. Permisos embedding habilitados