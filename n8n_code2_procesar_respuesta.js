// ⭐ CODE 2 - PROCESAR RESPUESTA DE IA (DESPUÉS DE AI AGENT)
// Este nodo procesa la respuesta de la IA y extrae datos para guardar

// 📤 Obtener respuesta del AI Agent
const respuestaIA = $input.first().json.text || $input.first().json.response || $input.first().json.output || "";

// 📤 Obtener datos del input anterior (puede venir del merge o del AI Agent)
const inputData = $input.all();
let webhookData = {};

// Buscar datos del webhook en el input
if (inputData && inputData.length > 0) {
    // Tomar el primer item que tenga session_id (datos del workflow)
    webhookData = inputData.find(item => item.json && item.json.session_id) || inputData[0];
    if (webhookData && webhookData.json) {
        webhookData = webhookData.json;
    }
}

// 🧠 Función para extraer información de la respuesta de la IA
function extraerInformacionRespuesta(respuestaTexto) {
    const respuestaLower = respuestaTexto.toLowerCase();
    
    // � Detectar sector de la respuesta
    const sectoresPalabras = {
        'naval': ['naval', 'mar', 'puerto', 'navegación', 'barco', 'marítimo', 'olas', 'marea', 'viento marino'],
        'agro': ['agrícola', 'cultivo', 'siembra', 'cosecha', 'campo', 'rural', 'agricultura', 'riego'],
        'aereo': ['aéreo', 'vuelo', 'aviación', 'aeropuerto', 'avión', 'cielo', 'viento en altura'],
        'energia': ['energía', 'eléctrico', 'solar', 'eólico', 'renovable', 'panel', 'turbina']
    };
    
    let sectorDetectado = null; // No asumir sector por defecto
    for (const [sector, palabras] of Object.entries(sectoresPalabras)) {
        if (palabras.some(palabra => respuestaLower.includes(palabra))) {
            sectorDetectado = sector;
            break;
        }
    }
    
    // 🌤️ Detectar datos meteorológicos mencionados
    const datosMeteorologicos = {
        temperatura: respuestaLower.includes('temperatura') || respuestaLower.includes('°c') || respuestaLower.includes('grados'),
        viento: respuestaLower.includes('viento') || respuestaLower.includes('km/h'),
        humedad: respuestaLower.includes('humedad') || respuestaLower.includes('%'),
        precipitacion: respuestaLower.includes('lluvia') || respuestaLower.includes('precipitación')
    };
    
    return {
        sector: sectorDetectado,
        datos_meteorologicos: datosMeteorologicos,
        respuesta_contiene_clima: Object.values(datosMeteorologicos).some(Boolean)
    };
}

// 🔍 Procesar respuesta de la IA
const infoExtraida = extraerInformacionRespuesta(respuestaIA);

// 🏗️ Construir datos para guardar en Supabase
const datosParaGuardar = {
    session_id: webhookData.session_id || `session_${Date.now()}`,
    user_id: webhookData.user_id || null,
    user_message: webhookData.chatInput || webhookData.message || "",
    ai_response: respuestaIA,
    
    // 📍 Ubicación como JSON string si existe
    ubicacion: webhookData.ubicacion ? JSON.stringify(webhookData.ubicacion) : null,
    
    // 🎯 Sector detectado de la respuesta real
    sector: infoExtraida.sector,
    
    // 📈 Metadatos como JSON string
    contexto_previo: JSON.stringify({
        intercambios_anteriores: webhookData.numero_intercambios_previos || 0,
        sector_conversacion: infoExtraida.sector,
        timestamp_inicio_sesion: webhookData.timestamp || new Date().toISOString(),
        contiene_datos_clima: infoExtraida.respuesta_contiene_clima
    }),
    
    // 📝 Metadatos como JSON string
    metadatos: JSON.stringify({
        user_agent: (webhookData.headers && webhookData.headers['user-agent']) || null,
        timestamp: new Date().toISOString(),
        processing_time: Date.now(),
        ai_agent_used: true,
        datos_meteorologicos_detectados: infoExtraida.datos_meteorologicos
    }),
    
    created_at: new Date().toISOString()
};

// 📤 RETORNAR EN FORMATO N8N (incluyendo campos para Edit Fields y subworkflows)
const outputCompleto = {
    // Para Supabase (conversaciones_memoria)
    ...datosParaGuardar,
    
    // Para Edit Fields (necesario para powerbi_url y texto_limpio)
    output: respuestaIA,
    
    // Campos procesados para subworkflows de gráficos
    powerbi_url: respuestaIA.match(/https:\/\/app\.powerbi\.com[^\s)]+/)?.[0] || null,
    texto_limpio: respuestaIA.replace(/.+?\)/g, "").trim() || respuestaIA,
    
    // Campos adicionales para el workflow
    ai_response_text: respuestaIA,
    sector_detectado: infoExtraida.sector,
    es_respuesta_climatica: infoExtraida.respuesta_contiene_clima
};

// 📤 RETORNAR EN FORMATO N8N 
return [outputCompleto];