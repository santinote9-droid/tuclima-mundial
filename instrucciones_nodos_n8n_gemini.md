# 🔧 INSTRUCCIONES ESPECÍFICAS PARA NODOS N8N (GEMINI 2.5-FLASH)

## 📋 **WORKFLOW: Naval_BI**

### Nodo 1: Webhook Trigger
**Descripción:** `Recibe consultas navales del chat principal`
**Path:** `/webhook/Naval_BI`
**HTTP Method:** `POST`
**Response Mode:** `Respond When Last Node Finishes`

### Nodo 2: Gemini Chat Model
**Descripción:** `Analiza consulta naval con contexto meteorológico marítimo`
**Model:** `models/gemini-2.5-flash`
**System Message:**
```
Eres un experto en meteorología marítima. Analiza las condiciones para navegación, puertos y actividades navales. 

Incluye SIEMPRE en tu respuesta:
- Puerto o ubicación específica
- Condiciones del mar (calma, agitado, etc.)
- Velocidad y dirección del viento  
- Temperatura del agua estimada
- Altura aproximada de las olas
- Visibilidad (excelente, buena, reducida)
- Recomendaciones de navegación

Responde de forma técnica pero comprensible para operadores portuarios.
```

### Nodo 3: Function - Formatear Datos Naval
**Descripción:** `Extrae y formatea datos navales para BigQuery`
**Código:**
```javascript
// Gemini response structure
const geminiResponse = $input.first().json.candidates[0].content.parts[0].text;
const originalData = $input.first().json.body || {};

// Extraer información específica naval
function extraerDatosNaval(texto) {
  const datos = {
    puerto: 'No especificado',
    viento_velocidad: null,
    viento_direccion: 'Variable',
    temperatura_agua: null,
    altura_olas: null,
    visibilidad: 'Buena'
  };
  
  // Extraer puerto (buscar patrones comunes)
  const puertosPatron = /puerto de ([a-záéíóúñ\s]+)|([a-záéíóúñ\s]+)\s+puerto/gi;
  const puertoMatch = texto.match(puertosPatron);
  if (puertoMatch) {
    datos.puerto = puertoMatch[0].replace(/puerto de /gi, '').replace(/ puerto/gi, '').trim();
  }
  
  // Extraer velocidad del viento
  const vientoVelPatron = /(\d+(?:\.\d+)?)\s*(?:km\/h|nudos|m\/s)/gi;
  const vientoMatch = texto.match(vientoVelPatron);
  if (vientoMatch) {
    datos.viento_velocidad = parseFloat(vientoMatch[0]);
  }
  
  // Extraer dirección del viento
  const direcciones = ['norte', 'sur', 'este', 'oeste', 'noreste', 'noroeste', 'sureste', 'suroeste'];
  for (const dir of direcciones) {
    if (texto.toLowerCase().includes(dir)) {
      datos.viento_direccion = dir;
      break;
    }
  }
  
  // Extraer altura de olas
  const olasPatron = /(\d+(?:\.\d+)?)\s*(?:metros|m)\s*(?:de\s*)?(?:olas|oleaje)/gi;
  const olasMatch = texto.match(olasPatron);
  if (olasMatch) {
    datos.altura_olas = parseFloat(olasMatch[0]);
  }
  
  // Extraer temperatura del agua
  const tempAguaPatron = /(?:agua|temperatura del mar).*?(\d+(?:\.\d+)?)\s*(?:°c|grados)/gi;
  const tempAguaMatch = texto.match(tempAguaPatron);
  if (tempAguaMatch) {
    datos.temperatura_agua = parseFloat(tempAguaMatch[1]);
  }
  
  return datos;
}

const datosNaval = extraerDatosNaval(geminiResponse);

const bigqueryData = {
  timestamp: new Date().toISOString(),
  session_id: originalData.sessionId || `naval-${Date.now()}`,
  puerto: datosNaval.puerto,
  condiciones_mar: datosNaval.condiciones_mar || 'Analizando',
  viento_velocidad: datosNaval.viento_velocidad,
  viento_direccion: datosNaval.viento_direccion,
  temperatura_agua: datosNaval.temperatura_agua,
  altura_olas: datosNaval.altura_olas,
  visibilidad: datosNaval.visibilidad,
  ai_analysis: geminiResponse,
  metadata: {
    workflow: 'Naval_BI',
    source: 'n8n',
    model: 'gemini-2.5-flash',
    original_query: originalData.chatInput || originalData.mensaje,
    processing_time: new Date().getTime()
  }
};

return [{ json: bigqueryData }];
```

### Nodo 4: Google BigQuery - Insertar Naval
**Descripción:** `Guarda datos navales en tabla BigQuery`
**Project ID:** `proyecto-bi-488218`
**Dataset:** `datos_clima`
**Table:** `naval`
**Operation:** `Insert`

### Nodo 5: Respond to Webhook
**Descripción:** `Devuelve respuesta de IA al chat principal`
**Response Body:** `{{ $('Gemini Chat Model').item.json.candidates[0].content.parts[0].text }}`

---

## 📋 **WORKFLOW: Agro_BI**

### Nodo 1: Webhook Trigger
**Descripción:** `Recibe consultas agrícolas del chat principal`
**Path:** `/webhook/Agro_BI`

### Nodo 2: Gemini Chat Model  
**Descripción:** `Analiza condiciones agrícolas y cultivos`
**Model:** `models/gemini-2.5-flash`
**System Message:**
```
Eres un experto en meteorología agrícola. Analiza condiciones para cultivos, siembra y cosecha.

Incluye SIEMPRE en tu respuesta:
- Tipo de cultivo mencionado
- Región o área geográfica
- Temperatura del suelo estimada
- Humedad relativa del aire
- Precipitación reciente/esperada
- Horas de sol disponibles
- Fase lunar actual
- Recomendaciones específicas para el cultivo

Responde de forma técnica para agricultores y agrónomos.
```

### Nodo 3: Function - Formatear Datos Agro
**Descripción:** `Extrae y formatea datos agrícolas para BigQuery`
**Código:**
```javascript
// Gemini response structure
const geminiResponse = $input.first().json.candidates[0].content.parts[0].text;
const originalData = $input.first().json.body || {};

function extraerDatosAgro(texto) {
  const datos = {
    cultivo: 'Cultivo general',
    region: 'No especificada',
    temperatura_suelo: null,
    humedad_relativa: null,
    precipitacion: null,
    horas_sol: null,
    fase_lunar: 'No especificada'
  };
  
  // Extraer cultivo
  const cultivos = ['maíz', 'trigo', 'soja', 'arroz', 'tomate', 'lechuga', 'papa', 'cebolla'];
  for (const cultivo of cultivos) {
    if (texto.toLowerCase().includes(cultivo)) {
      datos.cultivo = cultivo;
      break;
    }
  }
  
  // Extraer temperatura del suelo
  const tempSueloPatron = /(?:suelo|temperatura del suelo).*?(\d+(?:\.\d+)?)\s*(?:°c|grados)/gi;
  const tempSueloMatch = texto.match(tempSueloPatron);
  if (tempSueloMatch) {
    datos.temperatura_suelo = parseFloat(tempSueloMatch[1]);
  }
  
  // Extraer humedad
  const humedadPatron = /(?:humedad).*?(\d+(?:\.\d+)?)\s*(?:%|por\s*ciento)/gi;
  const humedadMatch = texto.match(humedadPatron);
  if (humedadMatch) {
    datos.humedad_relativa = parseFloat(humedadMatch[1]);
  }
  
  // Extraer precipitación
  const lluviaPatron = /(?:lluvia|precipitación).*?(\d+(?:\.\d+)?)\s*(?:mm|milímetros)/gi;
  const lluviaMatch = texto.match(lluviaPatron);
  if (lluviaMatch) {
    datos.precipitacion = parseFloat(lluviaMatch[1]);
  }
  
  return datos;
}

const datosAgro = extraerDatosAgro(geminiResponse);

const bigqueryData = {
  timestamp: new Date().toISOString(),
  session_id: originalData.sessionId || `agro-${Date.now()}`,
  cultivo: datosAgro.cultivo,
  region: datosAgro.region,
  temperatura_suelo: datosAgro.temperatura_suelo,
  humedad_relativa: datosAgro.humedad_relativa,
  precipitacion: datosAgro.precipitacion,
  horas_sol: datosAgro.horas_sol,
  fase_lunar: datosAgro.fase_lunar,
  ai_recommendations: geminiResponse,
  metadata: {
    workflow: 'Agro_BI',
    source: 'n8n',
    model: 'gemini-2.5-flash',
    original_query: originalData.chatInput || originalData.mensaje,
    processing_time: new Date().getTime()
  }
};

return [{ json: bigqueryData }];
```

### Nodo 4: Google BigQuery - Insertar Agro
**Descripción:** `Guarda datos agrícolas en tabla BigQuery`
**Table:** `agro`

---

## 📋 **WORKFLOW: Aereo_BI**

### Nodo 2: Gemini Chat Model
**Descripción:** `Analiza condiciones de vuelo y aeroportuarias`
**Model:** `models/gemini-2.5-flash`
**System Message:**
```
Eres un experto en meteorología aeronáutica. Analiza condiciones para vuelos y operaciones aeroportuarias.

Incluye SIEMPRE en tu respuesta:
- Aeropuerto(s) de origen y/o destino
- Altitud de vuelo típica
- Temperatura a la altitud de vuelo
- Corrientes de viento en altitud
- Visibilidad en km
- Condiciones atmosféricas (despejado, nublado, tormentoso)
- Recomendaciones de vuelo
- Posibles turbulencias

Responde de forma técnica para pilotos y controladores aéreos.
```

### Nodo 3: Function - Formatear Datos Aereo
**Descripción:** `Extrae y formatea datos aeronáuticos para BigQuery`
**Código:**
```javascript
// Gemini response structure
const geminiResponse = $input.first().json.candidates[0].content.parts[0].text;
const originalData = $input.first().json.body || {};

function extraerDatosAereo(texto) {
  const datos = {
    aeropuerto_origen: 'No especificado',
    aeropuerto_destino: 'No especificado', 
    altitud_vuelo: null,
    temperatura_altitud: null,
    visibilidad_km: null,
    condiciones_atmosfericas: 'Despejado'
  };
  
  // Extraer aeropuertos
  const aeropuertosPatron = /(?:aeropuerto|madrid|barcelona|valencia|sevilla|bilbao)/gi;
  const aeropuertos = texto.match(aeropuertosPatron);
  if (aeropuertos && aeropuertos.length >= 1) {
    datos.aeropuerto_origen = aeropuertos[0];
    if (aeropuertos.length >= 2) {
      datos.aeropuerto_destino = aeropuertos[1];
    }
  }
  
  // Extraer altitud
  const altitudPatron = /(\d+(?:\.\d+)?)\s*(?:metros|m|pies|ft)?\s*(?:de\s*)?(?:altitud|altura)/gi;
  const altitudMatch = texto.match(altitudPatron);
  if (altitudMatch) {
    datos.altitud_vuelo = parseFloat(altitudMatch[1]);
  }
  
  // Extraer visibilidad
  const visibilidadPatron = /(?:visibilidad).*?(\d+(?:\.\d+)?)\s*(?:km|kilómetros)/gi;
  const visibilidadMatch = texto.match(visibilidadPatron);
  if (visibilidadMatch) {
    datos.visibilidad_km = parseFloat(visibilidadMatch[1]);
  }
  
  return datos;
}

const datosAereo = extraerDatosAereo(geminiResponse);

const bigqueryData = {
  timestamp: new Date().toISOString(),
  session_id: originalData.sessionId || `aereo-${Date.now()}`,
  aeropuerto_origen: datosAereo.aeropuerto_origen,
  aeropuerto_destino: datosAereo.aeropuerto_destino,
  altitud_vuelo: datosAereo.altitud_vuelo,
  temperatura_altitud: datosAereo.temperatura_altitud,
  corrientes_viento: { descripcion: 'Extraído de IA', datos: 'En análisis' },
  visibilidad_km: datosAereo.visibilidad_km,
  condiciones_atmosfericas: datosAereo.condiciones_atmosfericas,
  ai_flight_analysis: geminiResponse,
  metadata: {
    workflow: 'Aereo_BI',
    source: 'n8n',
    model: 'gemini-2.5-flash',
    original_query: originalData.chatInput || originalData.mensaje,
    processing_time: new Date().getTime()
  }
};

return [{ json: bigqueryData }];
```

### Nodo 4: Google BigQuery - Insertar Aereo
**Descripción:** `Guarda datos aeronáuticos en tabla BigQuery`
**Table:** `aereo`

---

## 📋 **WORKFLOW: Energia_BI**

### Nodo 2: Gemini Chat Model
**Descripción:** `Analiza condiciones para energías renovables`
**Model:** `models/gemini-2.5-flash`
**System Message:**
```
Eres un experto en meteorología para energías renovables. Analiza condiciones para producción solar, eólica e hidroeléctrica.

Incluye SIEMPRE en tu respuesta:
- Tipo de energía (solar, eólica, hidroeléctrica)
- Ubicación específica
- Radiación solar (W/m² o similar)
- Velocidad del viento
- Temperatura ambiente
- Eficiencia estimada en %
- Producción estimada en kWh
- Recomendaciones de optimización

Responde de forma técnica para ingenieros energéticos.
```

### Nodo 3: Function - Formatear Datos Energia
**Descripción:** `Extrae y formatea datos energéticos para BigQuery`
**Código:**
```javascript
// Gemini response structure
const geminiResponse = $input.first().json.candidates[0].content.parts[0].text;
const originalData = $input.first().json.body || {};

function extraerDatosEnergia(texto) {
  const datos = {
    tipo_energia: 'solar',
    ubicacion: 'No especificada',
    radiacion_solar: null,
    velocidad_viento: null,
    temperatura_ambiente: null,
    eficiencia_estimada: null,
    produccion_kwh: null
  };
  
  // Extraer tipo de energía
  if (texto.toLowerCase().includes('eólica') || texto.toLowerCase().includes('viento')) {
    datos.tipo_energia = 'eolica';
  } else if (texto.toLowerCase().includes('hidro') || texto.toLowerCase().includes('agua')) {
    datos.tipo_energia = 'hidroelectrica';
  } else {
    datos.tipo_energia = 'solar';
  }
  
  // Extraer radiación solar
  const radiacionPatron = /(\d+(?:\.\d+)?)\s*(?:w\/m²|watts)/gi;
  const radiacionMatch = texto.match(radiacionPatron);
  if (radiacionMatch) {
    datos.radiacion_solar = parseFloat(radiacionMatch[1]);
  }
  
  // Extraer eficiencia
  const eficienciaPatron = /(?:eficiencia).*?(\d+(?:\.\d+)?)\s*(?:%|por\s*ciento)/gi;
  const eficienciaMatch = texto.match(eficienciaPatron);
  if (eficienciaMatch) {
    datos.eficiencia_estimada = parseFloat(eficienciaMatch[1]);
  }
  
  // Extraer producción
  const produccionPatron = /(\d+(?:\.\d+)?)\s*(?:kwh|kilowatt)/gi;
  const produccionMatch = texto.match(produccionPatron);
  if (produccionMatch) {
    datos.produccion_kwh = parseFloat(produccionMatch[1]);
  }
  
  return datos;
}

const datosEnergia = extraerDatosEnergia(geminiResponse);

const bigqueryData = {
  timestamp: new Date().toISOString(),
  session_id: originalData.sessionId || `energia-${Date.now()}`,
  tipo_energia: datosEnergia.tipo_energia,
  ubicacion: datosEnergia.ubicacion,
  radiacion_solar: datosEnergia.radiacion_solar,
  velocidad_viento: datosEnergia.velocidad_viento,
  temperatura_ambiente: datosEnergia.temperatura_ambiente,
  eficiencia_estimada: datosEnergia.eficiencia_estimada,
  produccion_kwh: datosEnergia.produccion_kwh,
  ai_efficiency_analysis: geminiResponse,
  metadata: {
    workflow: 'Energia_BI',
    source: 'n8n',
    model: 'gemini-2.5-flash',
    original_query: originalData.chatInput || originalData.mensaje,
    processing_time: new Date().getTime()
  }
};

return [{ json: bigqueryData }];
```

### Nodo 4: Google BigQuery - Insertar Energia
**Descripción:** `Guarda datos energéticos en tabla BigQuery`
**Table:** `energia`

---

## 🧠 **DESCRIPTIONS para "Call n8n workflow tool"**

### **Naval_BI - Description:**
```
Use this workflow for maritime, naval, port, and ocean-related weather queries. Handles questions about:
- Port conditions and harbor weather
- Ship navigation and maritime safety
- Ocean temperature, waves, and sea conditions  
- Coastal weather and marine forecasts
- Fishing conditions and boat operations
- Tide information and nautical weather

Keywords to trigger: puerto, mar, naval, barco, navegar, océano, costa, marea, pesca, marinero, harbor, ship, ocean, maritime, port, sailing, waves, sea
```

### **Agro_BI - Description:**
```
Use this workflow for agricultural, farming, and crop-related weather queries. Handles questions about:
- Crop growing conditions and agricultural forecasts
- Soil temperature and moisture levels
- Planting, harvesting, and farming schedules
- Livestock and animal husbandry weather needs
- Irrigation and agricultural water management
- Pest and disease weather conditions

Keywords to trigger: cultivo, agricultura, cosecha, siembra, granja, ganado, campo, suelo, riego, agricultor, crop, farming, agriculture, harvest, livestock, soil, irrigation
```

### **Aereo_BI - Description:**
```
Use this workflow for aviation, flight, and airport-related weather queries. Handles questions about:
- Flight conditions and aviation weather
- Airport operations and runway conditions  
- Pilot weather briefings and flight planning
- Aircraft performance and altitude weather
- Turbulence, visibility, and ceiling conditions
- Drone operations and small aircraft weather

Keywords to trigger: vuelo, avión, aeropuerto, piloto, aviación, despegue, aterrizaje, turbulencia, altitud, flight, airplane, airport, pilot, aviation, takeoff, landing, aircraft
```

### **Energia_BI - Description:**
```
Use this workflow for renewable energy and power generation weather queries. Handles questions about:
- Solar panel efficiency and solar radiation
- Wind turbine conditions and wind energy
- Hydroelectric power and water flow conditions
- Energy production optimization
- Weather impact on power generation
- Renewable energy forecasting and planning

Keywords to trigger: energía, solar, eólica, renovable, paneles, turbina, electricidad, generación, eficiencia, energy, solar, wind, renewable, panels, turbine, electricity, power
```

---

## ⚙️ **CONFIGURACIÓN GENERAL BIGQUERY NODES**

### Para TODOS los nodos Google BigQuery:
**Resource:** `Insert`
**Project ID:** `proyecto-bi-488218` 
**Dataset:** `datos_clima`
**Credentials:** Usar tu service account JSON existente

### Auto Create Table: `TRUE`
### Ignore Unknown Values: `TRUE`
### Skip Invalid Rows: `FALSE`

---

## ⚠️ **CAMBIOS IMPORTANTES PARA GEMINI:**

1. **Estructura de Respuesta:** 
   - OpenAI: `choices[0].message.content`
   - **Gemini:** `candidates[0].content.parts[0].text`

2. **Response Webhook:** 
   - Cambiar a: `$('Gemini Chat Model').item.json.candidates[0].content.parts[0].text`

3. **Metadata Adicional:**
   - Agregado campo `"model": "gemini-2.5-flash"` para tracking

4. **System Messages:**
   - Los prompts funcionan igual con Gemini
   - Posiblemente mejores resultados en español

---

## 🧪 **DATOS DE PRUEBA PARA CADA WEBHOOK**

### Test Naval:
```json
{
  "chatInput": "Condiciones navales para Puerto de Barcelona mañana",
  "sessionId": "test-naval-gemini-123"
}
```

### Test Agro:
```json
{
  "chatInput": "Condiciones para cultivo de maíz en Valencia esta semana", 
  "sessionId": "test-agro-gemini-123"
}
```

### Test Aereo:
```json
{
  "chatInput": "Condiciones de vuelo Madrid-Barcelona hoy por la tarde",
  "sessionId": "test-aereo-gemini-123"
}
```

### Test Energia:
```json
{
  "chatInput": "Eficiencia solar y eólica en Andalucía para el fin de semana",
  "sessionId": "test-energia-gemini-123"
}
```