# 🔧 CONFIGURACIÓN WORKFLOW N8N PARA GRÁFICOS DINÁMICOS

## 🎯 WORKFLOW ACTUALIZADO PARA CHAT + POWER BI

### 📋 NODOS REQUERIDOS:

#### 1. **WEBHOOK TRIGGER** (Ya existente)
- **URL**: `https://n8n-production-2651.up.railway.app/webhook/chat`
- **Método**: POST
- **Datos recibidos**: `chatInput`, `sessionId`, `data00` (archivos)

#### 2. **FUNCTION NODE: Procesador de Intención**
```javascript
// 🧠 DETECTAR INTENCIÓN DEL USUARIO

const userInput = $json.chatInput || "";
const sessionId = $json.sessionId || "";

// Obtener contexto de la sesión (si existe en base de datos)
const sessionData = {
    currentPage: "naval", // Detectar desde headers o parámetro
    location: { lat: -34.5794, lon: -58.5944 }, // Buenos Aires por defecto
    previousContext: ""
};

// Cargar la función de procesamiento
const { procesarPeticionGrafico } = require('./powerbi_generator');

// Procesar la petición
const resultadoGrafico = procesarPeticionGrafico(userInput, sessionData);

// Determinar el tipo de respuesta
let tipoRespuesta = "texto";
let respuestaComoTexto = "";
let urlPowerBI = "";

if (resultadoGrafico && resultadoGrafico.mostrarGrafico) {
    tipoRespuesta = "grafico";
    urlPowerBI = resultadoGrafico.urlPowerBI;
    respuestaComoTexto = resultadoGrafico.respuesta;
} else {
    // Es una consulta normal, enviar a IA
    tipoRespuesta = "ia_normal";
    respuestaComoTexto = userInput; // Pasar a nodo de IA
}

return [{
    json: {
        sessionId: sessionId,
        userInput: userInput,
        tipoRespuesta: tipoRespuesta,
        urlPowerBI: urlPowerBI,
        respuestaGrafico: respuestaComoTexto,
        sessionData: sessionData
    }
}];
```

#### 3. **FUNCTION NODE: Analizador de Intención Power BI**
```javascript
// 🚀 IMPORTAR LÓGICA DE GENERACIÓN POWER BI
// (Pegar aquí todo el código de n8n_powerbi_generator.js)

const userInput = $json.userInput;
const sessionData = {
    currentPage: $json.sector,
    location: $json.location
};

// Procesar petición usando la lógica actualizada
const resultadoGrafico = procesarPeticionGrafico(userInput, sessionData);

if (resultadoGrafico && resultadoGrafico.mostrarGrafico) {
    return [{
        json: {
            ...$json,
            tipoRespuesta: "grafico",
            urlPowerBI: resultadoGrafico.urlPowerBI,
            respuestaGrafico: resultadoGrafico.respuesta
        }
    }];
} else {
    return [{
        json: {
            ...$json,
            tipoRespuesta: "chat_normal"
        }
    }];
}
```

#### 4. **IF NODE: Decisión Power BI vs Chat Normal**
```
Condición: {{ $json.tipoRespuesta === "grafico" }}
TRUE → Enviar respuesta con gráfico
FALSE → Procesar con BigQuery + IA normal
```

#### 5. **FUNCTION NODE: Respuesta Power BI** (Ruta TRUE)
```javascript
// 📊 PREPARAR RESPUESTA CON GRÁFICO DINÁMICO

const respuesta = $json.respuestaGrafico;
const urlPowerBI = $json.urlPowerBI;
const sector = $json.sector;

return [{
    json: {
        output: respuesta,
        metadata: {
            type: "graph_response",
            powerBiUrl: urlPowerBI,
            sector: sector
        },
        sessionId: $json.sessionId
    }
}];
```

#### 6. **FUNCTION NODE: Preparar Datos BigQuery** (Ruta FALSE)
```javascript
// 🚀 PREPARAR DATOS PARA BIGQUERY SEGUN SECTOR

const sector = $json.sector;
const userInput = $json.userInput;
const sessionId = $json.sessionId;
const location = $json.location;
const timestamp = new Date().toISOString();

// Datos base para todos los sectores
let dataForBigQuery = {
    timestamp: timestamp,
    session_id: sessionId
};

// Datos específicos según sector
switch(sector) {
    case "naval":
        dataForBigQuery.puerto = "Buenos Aires"; // Extraer de input o usar default
        dataForBigQuery.condiciones_mar = "Consulta usuario"; 
        dataForBigQuery.viento_velocidad = 0;
        dataForBigQuery.viento_direccion = "";
        dataForBigQuery.temperatura_agua = 0;
        dataForBigQuery.altura_olas = 0;
        dataForBigQuery.visibilidad = 0;
        dataForBigQuery.ai_analysis = userInput;
        break;
        
    case "agro":
        dataForBigQuery.cultivo = "General";
        dataForBigQuery.region = location.region || "Buenos Aires";
        dataForBigQuery.temperatura_suelo = 0;
        dataForBigQuery.humedad_relativa = 0;
        dataForBigQuery.precipitacion = 0;
        dataForBigQuery.horas_sol = 0;
        dataForBigQuery.fase_lunar = "";
        dataForBigQuery.ai_recommendations = userInput;
        break;
        
    case "aereo":
        dataForBigQuery.aeropuerto_origen = "";
        dataForBigQuery.aeropuerto_destino = "";
        dataForBigQuery.altitud_vuelo = 0;
        dataForBigQuery.temperatura_altitud = 0;
        dataForBigQuery.corrientes_viento = JSON.stringify({});
        dataForBigQuery.visibilidad_km = 0;
        dataForBigQuery.condiciones_atmosfericas = "";
        dataForBigQuery.ai_flight_analysis = userInput;
        break;
        
    case "energia":
        dataForBigQuery.tipo_energia = "Solar";
        dataForBigQuery.ubicacion = JSON.stringify(location);
        dataForBigQuery.radiacion_solar = 0;
        dataForBigQuery.velocidad_viento = 0;
        dataForBigQuery.temperatura_ambiente = 0;
        dataForBigQuery.eficiencia_estimada = 0;
        dataForBigQuery.produccion_kwh = 0;
        dataForBigQuery.ai_efficiency_analysis = userInput;
        break;
}

dataForBigQuery.metadata = JSON.stringify({
    source: "chat",
    location: location,
    userQuery: userInput
});

return [{
    json: {
        ...dataForBigQuery,
        sector: sector,
        originalInput: userInput
    }
}];
```

#### 7. **GOOGLE BIGQUERY NODE: Insertar Datos** (Ruta FALSE)
```
Operation: Insert
Table: Usar tabla dinámica según sector:
- Si sector = "naval" → NAVAL_BI  
- Si sector = "agro" → AGRO_BI
- Si sector = "aereo" → AEREO_BI
- Si sector = "energia" → ENERGIA_BI

Parámetros: (Usar los parámetros existentes de parametros_n8n_corregidos.txt)
Ejemplo para NAVAL_BI:
@timestamp = {{ $('Preparar Datos BigQuery').item.json.timestamp }}
@session_id = {{ $('Preparar Datos BigQuery').item.json.session_id }}
@puerto = {{ $('Preparar Datos BigQuery').item.json.puerto }}
@condiciones_mar = {{ $('Preparar Datos BigQuery').item.json.condiciones_mar }}
... (todos los demás parámetros)
```

#### 8. **GOOGLE AI NODE: Procesamiento IA** (Después de BigQuery)
```
Prompt del Sistema:
Eres un experto asistente meteorológico para TuClima IA especializado en el sector {{ $json.sector }}.

DATO S DE CONTEXTO:
- Sector: {{ $json.sector }}
- Sesión: {{ $json.session_id }}
- Ubicación: {{ JSON.stringify($json.location) }}
- Datos insertados en BigQuery: SÍ

INSTRUCCIONES SECTOR ESPECÍFICAS:
{% if $json.sector === "naval" %}
- Especializa en condiciones marítimas, vientos, olas, navegación
- Usa términos técnicos navales
- Considera puertos y rutas marítimas
{% elif $json.sector === "agro" %}
- Especializa en cultivos, suelo, precipitación, fases lunares
- Usa términos agronómicos
- Considera regiones agrícolas
{% elif $json.sector === "aereo" %}
- Especializa en condiciones de vuelo, altitud, turbulencias
- Usa términos aeronáuticos
- Considera aeropuertos y rutas aéreas
{% elif $json.sector === "energia" %}
- Especializa en energía renovable, eficiencia, radiación solar
- Usa términos energéticos
- Considera instalaciones energéticas
{% endif %}

Si el usuario quiere gráficos o visualizaciones, responde:
"[MOSTRAR_GRAFICO] Te genero la visualización que necesitas para el sector {{ $json.sector }}"

CONSULTA DEL USUARIO: {{ $json.originalInput }}
```

#### 6. **MERGE NODE: Combinar Respuestas**
```
Mode: Merge by Index
```

#### 7. **FUNCTION NODE: Respuesta Final**
```javascript
// 🎯 FORMATEAR RESPUESTA FINAL

const tipoRespuesta = $json.tipoRespuesta;
let output = "";
let metadata = {};

if (tipoRespuesta === "grafico") {
    output = $("Respuesta Gráfico").first().json.output;
    metadata.powerBiUrl = $("Respuesta Gráfico").first().json.powerBiUrl;
    metadata.type = "graph_response";
} else {
    output = $("Google AI").first().json.output || $("Google AI").first().json.text || "Respuesta procesada";
    metadata.type = "text_response";
}

return [{
    json: {
        output: output,
        metadata: metadata,
        sessionId: $json.sessionId,
        timestamp: new Date().toISOString()
    }
}];
```

#### 8. **WEBHOOK RESPONSE** (Existente)
```
Response Body: {{ $json }}
Status Code: 200
```

---

## 🗃️ BASE DE DATOS / MEMORY STORE

### Tabla de Sesiones (Recomendado):
```sql
CREATE TABLE chat_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    current_page VARCHAR(50),
    location_lat DECIMAL(10,8),
    location_lon DECIMAL(11,8),
    preferences JSON,
    last_activity TIMESTAMP,
    context JSON
);
```

### 💾 Nodo Memory Store (Alternativo):
```javascript
// Guardar contexto de sesión
const sessionId = $json.sessionId;
const sessionData = {
    currentPage: $json.sessionData.currentPage,
    location: $json.sessionData.location,
    lastInteraction: new Date().toISOString(),
    chartHistory: []
};

// Guardar en memoria de N8N
return [{
    json: {
        key: `session_${sessionId}`,
        value: JSON.stringify(sessionData),
        ...sessionData
    }
}];
```

---

## 🎛️ VARIABLES DE ENTORNO

### En N8N Settings:
```
POWERBI_BASE_URL=https://app.powerbi.com/view?r=eyJrIjoiOGVkMzlkY2QtYjJmOC00NmY3LTkzOWYtMTE5NTljYzAxOGJhIiwidCI6IjU4MWJhNzMyLTczYWUtNDhiZC1iNmQ2LTY4ZTA0NzYxNjA4OCIsImMiOjR9

POWERBI_REPORT_PAGES={
  "dashboard": "&pageName=ReportSection_Dashboard",
  "lineal": "&pageName=ReportSection_Lineal", 
  "mapa": "&pageName=ReportSection_Mapa",
  "comparativa": "&pageName=ReportSection_Comparativa",
  "predictivo": "&pageName=ReportSection_Predictivo"
}

GOOGLE_AI_API_KEY=tu_api_key_aqui
DEFAULT_LOCATION={"lat": -34.5794, "lon": -58.5944}
```

---

## 🧪 TESTING

### Casos de Prueba:

#### Test 1: Solicitud de gráfico básico
```
Input: "muéstrame un gráfico de temperatura de hoy"
Expected: Respuesta con [MOSTRAR_GRAFICO] y URL de Power BI
```

#### Test 2: Consulta normal
```
Input: "¿qué tiempo hay en Buenos Aires?"
Expected: Respuesta de IA normal sin gráfico
```

#### Test 3: Comparativas
```
Input: "compara viento entre naval y aereo"
Expected: URL de Power BI con filtros específicos
```

#### Test 4: Mapas
```
Input: "dónde llueve más en Argentina"
Expected: URL de Power BI con vista de mapa
```

---

## 🔄 FLUJO DE IMPLEMENTACIÓN

### Paso 1: Preparar Power BI
1. Crear las páginas del reporte según configuración
2. Configurar parámetros y filtros
3. Probar URLs manuales

### Paso 2: Actualizar N8N
1. Duplicar workflow actual
2. Agregar nuevos nodos de decisión
3. Implementar función de análisis de intención
4. Testing completo

### Paso 3: Integración
1. Actualizar frontend para manejar nuevas respuestas
2. Test de integración completa
3. Deploy y monitoring

---

## 📈 MÉTRICAS Y MONITORING

### KPIs a medir:
- % solicitudes que generan gráficos
- Tiempo de respuesta promedio
- Tipos de gráficos más solicitados
- Errores en generación de URLs

### Logging recomendado:
```javascript
// En cada nodo importante
console.log(`[${timestamp}] SessionID: ${sessionId} | Action: ${action} | Success: ${success}`);
```