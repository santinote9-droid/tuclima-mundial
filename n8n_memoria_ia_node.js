// ⭐ CODE 1 - SOLO CONTEXTO Y MEMORIA (ANTES DE IA)
// Este nodo SOLO prepara el contexto de memoria para la IA

const userMessage = $('Webhook').first().json.body.chatInput || $('Webhook').first().json.body.message || "";
const sessionId = $('Webhook').first().json.body.sessionId || $('Webhook').first().json.body.session_id || `session_${Date.now()}`;
const userId = $('Webhook').first().json.body.userId || $('Webhook').first().json.body.user_id || null;

// 🕐 CONFIGURACIÓN DE MEMORIA
const LIMITE_MENSAJES_MEMORIA = 10; // Últimos 10 intercambios
const LIMITE_CARACTERES_CONTEXTO = 4000; // Para evitar overflow de tokens

// 🧠 FUNCIÓN PRINCIPAL DE MEMORIA
function construirContextoMemoria() {
    // Obtener datos del nodo Supabase anterior
    const inputData = $input.all();
    let datosMemoria = [];
    
    // Manejar diferentes casos de input
    if (inputData && inputData.length > 0) {
        // Si hay datos del nodo Supabase
        datosMemoria = inputData.map(item => item.json).filter(item => item && item.session_id);
    }
    
    if (!datosMemoria || datosMemoria.length === 0) {
        return {
            contexto_conversacion: "",
            es_primera_interaccion: true,
            numero_intercambios: 0,
            memoria_completa: []
        };
    }
    
    // 🔄 CONSTRUIR CONTEXTO DE CONVERSACIÓN
    let contextoTexto = "\\n### 📝 MEMORIA DE CONVERSACIÓN PREVIA ###\\n";
    let caracteresUsados = 0;
    let intercambiosIncluidos = 0;
    
    // Ordenar internamente por fecha (más antiguo a más nuevo para el contexto)
    // Ya que en n8n reciente puede no venir ordenado desde Supabase
    const memoriaOrdenada = datosMemoria
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .slice(-LIMITE_MENSAJES_MEMORIA); // Solo últimos X mensajes
    
    for (const intercambio of memoriaOrdenada) {
        const lineaUsuario = `Usuario: ${intercambio.user_message}`;
        const lineaIA = `IA: ${intercambio.ai_response}`;
        const bloque = `${lineaUsuario}\\n${lineaIA}\\n\\n`;
        
        if (caracteresUsados + bloque.length > LIMITE_CARACTERES_CONTEXTO) {
            break; // No exceder límite de caracteres
        }
        
        contextoTexto += bloque;
        caracteresUsados += bloque.length;
        intercambiosIncluidos++;
    }
    
    contextoTexto += "### FIN MEMORIA ###\\n\\n";
    
    return {
        contexto_conversacion: contextoTexto,
        es_primera_interaccion: intercambiosIncluidos === 0,
        numero_intercambios: intercambiosIncluidos,
        memoria_completa: datosMemoria
    };
}

// �️ CONSTRUIR OUTPUT SIMPLIFICADO (SOLO MEMORIA)
const memoriaInfo = construirContextoMemoria();

const outputCompleto = {
    // 📤 Datos originales del webhook (sin modificar)
    ...($('Webhook').first().json.body),
    
    // 🧠 Información de memoria para la IA
    session_id: sessionId,
    user_id: userId,
    contexto_memoria: memoriaInfo.contexto_conversacion,
    es_primera_vez: memoriaInfo.es_primera_interaccion,
    numero_intercambios_previos: memoriaInfo.numero_intercambios,
    
    // 📝 Instrucciones de memoria para la IA
    instrucciones_memoria: memoriaInfo.es_primera_interaccion 
        ? "Esta es la primera interacción con este usuario. Preséntate de forma amigable."
        : `Has tenido ${memoriaInfo.numero_intercambios} intercambios previos con este usuario. Mantén la continuidad de la conversación basándote en el contexto previo.`
};

// 📤 RETORNAR DATOS EN FORMATO N8N
return [outputCompleto];