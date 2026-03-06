/**
 * 💾 GUARDAR RESPUESTA DE IA - N8N FUNCTION NODE
 * 
 * Este nodo va DESPUÉS de que la IA responde y:
 * 1. Formatea los datos para guardar en Supabase
 * 2. Prepara la respuesta final para el webhook response
 */

// 📥 DATOS DE ENTRADA (vienen del nodo anterior de IA)
const aiResponse = $json.ai_response || $json.response || $json.answer || "";
const sessionId = $json.session_id || $json.sessionId;
const userId = $json.user_id || $json.userId;
const userMessage = $json.user_message || $json.message;
const sectorActual = $json.sector_actual || $json.sector || "general";
const ubicacion = $json.ubicacion || { lat: -34.5794, lon: -58.5944 };
const datosParaGuardar = $json.datos_para_guardar || {};

// ⚡ LIMPIAR Y VALIDAR RESPUESTA DE IA
function limpiarRespuestaIA(respuesta) {
    if (!respuesta || respuesta.trim() === "") {
        return "Lo siento, hubo un problema procesando tu consulta. Por favor intenta de nuevo.";
    }
    
    // Limpiar caracteres raros o escapes innecesarios
    return respuesta
        .replace(/\\n/g, '\\n')
        .replace(/\\"/g, '"')
        .trim();
}

// 📝 PREPARAR DATOS PARA INSERCIÓN EN SUPABASE
const respuestaLimpia = limpiarRespuestaIA(aiResponse);

const registroConversacion = {
    session_id: sessionId,
    user_id: userId,
    user_message: userMessage,
    ai_response: respuestaLimpia,
    sector: sectorActual,
    ubicacion: ubicacion,
    contexto_previo: datosParaGuardar.contexto_previo || {},
    metadatos: {
        ...datosParaGuardar.metadatos,
        response_length: respuestaLimpia.length,
        response_timestamp: new Date().toISOString(),
        execution_time_ms: Date.now() - (datosParaGuardar.start_time || Date.now())
    }
};

// 🎯 PREPARAR RESPUESTA FINAL PARA WEBHOOK
const respuestaFinal = {
    // Para el frontend
    success: true,
    response: respuestaLimpia,
    sessionId: sessionId,
    sector: sectorActual,
    timestamp: new Date().toISOString(),
    
    // Para debugging (opcional, quitar en producción)
    debug: {
        user_message: userMessage,
        response_length: respuestaLimpia.length,
        sector_detectado: sectorActual,
        memoria_activada: true
    }
};

// 📤 RETORNAR AMBOS: datos para Supabase Y respuesta para webhook
return [{
    // Este output va al nodo INSERT de Supabase
    json: {
        supabase_insert: registroConversacion,
        webhook_response: respuestaFinal
    }
}];

/**
 * 📋 FLOW COMPLETO EN N8N:
 * 
 * 1. Webhook Trigger (recibe chatInput, sessionId)
 * 2. Supabase GET (obtener memoria) → memoria_anterior
 * 3. Function: Procesar Memoria (este archivo anterior) → contexto para IA
 * 4. IA Node (OpenAI/Claude con contexto) → ai_response
 * 5. Function: Preparar Guardado (este archivo) → datos preparados
 * 6. Supabase INSERT (guardar conversación) + Webhook Response (responder al frontend)
 * 
 * CONFIGURACIÓN SUPABASE INSERT DESPUÉS DE ESTE NODO:
 * - Tabla: conversaciones_memoria
 * - Datos: {{ $json.supabase_insert }}
 * 
 * CONFIGURACIÓN WEBHOOK RESPONSE:
 * - Datos: {{ $json.webhook_response }}
 */