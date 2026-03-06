// � FUNCIÓN PROFESIONAL N8N - PROCESAMIENTO DE DATOS SECTORIALES
// ✅ SIN VALORES PREDETERMINADOS | ✅ OPTIMIZADO | ✅ ANTI-TIMEOUT

try {
  // 📥 EXTRACCIÓN SEGURA DE DATOS usando sintaxis correcta para "Run Once for Each Item"
  let inputData = {};
  let aiResponse = "";
  
  // Obtener datos del item actual (no .all() sino .item)
  const currentItem = $input.item.json || {};
  
  // Los datos del webhook vienen en el body o directamente en json
  inputData = currentItem.body || currentItem;
  
  // Extraer respuesta de IA si existe (viene del nodo AI Agent anterior)
  if (currentItem.choices && currentItem.choices[0]) {
    // OpenAI format
    aiResponse = currentItem.choices[0].message?.content || "";
  } else if (currentItem.candidates && currentItem.candidates[0]) {
    // Gemini API format
    aiResponse = currentItem.candidates[0].content?.parts?.[0]?.text || "";
  } else if (currentItem.content) {
    // Direct AI response
    aiResponse = currentItem.content;
  } else if (currentItem.text) {
    // Alternative text field
    aiResponse = currentItem.text;
  }
  
  // 🔍 DETECCIÓN INTELIGENTE DEL SECTOR
  const chatInput = inputData.chatInput || inputData.mensaje || "";
  let sector = "GENERAL";
  
  if (/puerto|barco|nav[ía]o|naval|mar[íi]timo|costa/i.test(chatInput)) {
    sector = "NAVAL";
  } else if (/energ[íi]a|el[ée]ctric|solar|e[óo]lic|combustible/i.test(chatInput)) {
    sector = "ENERGIA"; 
  } else if (/agr[íi]cola|cultivo|cosecha|campo|siembra/i.test(chatInput)) {
    sector = "AGRO";
  } else if (/a[ée]reo|vuelo|avi[óo]n|aeropuerto|aerodin[áa]mic/i.test(chatInput)) {
    sector = "AEREO";
  }
  
  // 📊 EXTRACCIÓN DE MÉTRICAS NUMÉRICAS
  const extractNumber = (text, pattern, defaultVal = null) => {
    const match = text.match(pattern);
    if (match && match[1]) {
      const num = parseFloat(match[1]);
      return !isNaN(num) ? num : defaultVal;
    }
    return defaultVal;
  };
  
  const extractLocation = (text) => {
    // Buscar patrones de ubicación
    const patterns = [
      /(?:puerto|port)[^a-zA-ZñÑ]*([a-zA-ZñÑ\s]{3,30})/i,
      /(?:ciudad|city)[^a-zA-ZñÑ]*([a-zA-ZñÑ\s]{3,30})/i,
      /(?:en|at|zona)[^a-zA-ZñÑ]*([a-zA-ZñÑ\s]{3,30})/i
    ];
    
    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match && match[1]) {
        return match[1].trim().substring(0, 100);
      }
    }
    return null;
  };
  
  // 🏗️ CONSTRUCCIÓN DE DATOS ESTRUCTURADOS
  const processedData = {
    timestamp: new Date().toISOString(),
    session_id: inputData.sessionId || `auto-${Date.now()}`,
    sector: sector,
    chat_input: chatInput.substring(0, 1000), // Limitar longitud
    ai_response: aiResponse.substring(0, 5000), // Limitar longitud
    location: extractLocation(chatInput),
    
    // 🌊 DATOS NAVALES
    puerto: sector === "NAVAL" ? extractLocation(chatInput) : null,
    condiciones_mar: null,
    altura_olas: extractNumber(chatInput, /olas?[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    
    // 💨 DATOS METEOROLÓGICOS
    viento_velocidad: extractNumber(chatInput, /viento[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    viento_direccion: null,
    temperatura: extractNumber(chatInput, /temperatura[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    temperatura_agua: extractNumber(chatInput, /agua[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    humedad: extractNumber(chatInput, /humedad[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    presion: extractNumber(chatInput, /presi[óo]n[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    visibilidad: extractNumber(chatInput, /visibilidad[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    
    // 🌾 DATOS AGRÍCOLAS
    tipo_cultivo: sector === "AGRO" ? extractLocation(chatInput) : null,
    fase_cultivo: null,
    humedad_suelo: extractNumber(chatInput, /suelo[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    
    // ⚡ DATOS ENERGÉTICOS
    tipo_energia: sector === "ENERGIA" ? extractLocation(chatInput) : null,
    capacidad: extractNumber(chatInput, /capacidad[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    eficiencia: extractNumber(chatInput, /eficiencia[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    
    // ✈️ DATOS AÉREOS  
    aeropuerto: sector === "AEREO" ? extractLocation(chatInput) : null,
    altitud: extractNumber(chatInput, /altitud[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    velocidad_viento: extractNumber(chatInput, /velocidad[^0-9]*([0-9]+(?:\.[0-9]+)?)/i),
    
    // 📋 METADATOS
    metadata: JSON.stringify({
      source: "n8n_function",
      processing_timestamp: Date.now(),
      workflow_version: "v2.0",
      input_length: chatInput.length,
      ai_response_length: aiResponse.length
    })
  };
  
  // 🎯 RETORNO OPTIMIZADO usando sintaxis correcta n8n
  return processedData;
  
} catch (error) {
  // 🚨 MANEJO DE ERRORES ROBUSTO  
  console.error('Function Node Error:', error.message);
  return {
    timestamp: new Date().toISOString(),
    session_id: `error-${Date.now()}`,
    sector: "ERROR",
    chat_input: "Error en procesamiento",
    ai_response: `Error: ${error.message}`,
    location: null,
    metadata: JSON.stringify({
      error: true,
      error_message: error.message,
      error_timestamp: Date.now()
    })
  };
}