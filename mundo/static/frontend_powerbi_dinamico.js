/**
 * 🌐 ACTUALIZACIONES FRONTEND PARA POWER BI DINÁMICO
 * 
 * Este código actualiza el chat existente para manejar URLs dinámicas
 * y respuestas contextual  es de la IA
 */

// 🔧 CONFIGURACIÓN ACTUALIZADA PARA NAVAL.HTML, AGRO.HTML, AEREO.HTML, ENERGIA.HTML

const urlN8N = "https://n8n-production-2651.up.railway.app/webhook/chat"; // Sin cambios
let sessionId = localStorage.getItem("chatSessionId") || generateUUID();
localStorage.setItem("chatSessionId", sessionId);

// 📊 NUEVA VARIABLE PARA GESTIONAR URLs DINÁMICAS
let currentPowerBiUrl = ""; // Se actualiza dinámicamente

// 🎯 FUNCIÓN ACTUALIZADA PARA ENVIAR MENSAJES
async function enviarMensaje() {
    const input = document.getElementById("user-input");
    const fileInput = document.getElementById("file-input");
    const filePreview = document.getElementById("file-preview");
    const chatBox = document.getElementById("chat-box");
    const texto = input.value.trim();
    const archivo = fileInput.files[0];

    if (!texto && !archivo) return;

    // Detectar página actual para contexto
    const currentPage = detectarPaginaActual();
    
    // Guardar en historial
    if (texto) {
        historialMensajes.push(texto);
        indiceHistorial = -1;
    }

    // Mostrar mensaje del usuario en UI
    let icon = generarIconoArchivo(archivo);
    chatBox.innerHTML += `<div class="message user-msg"><b>Tú:</b> ${texto} ${archivo ? `<br>${icon} <i>Archivo: ${archivo.name}</i>` : ''}</div>`;
    input.value = "";
    filePreview.innerHTML = '';
    chatBox.scrollTop = chatBox.scrollHeight;

    // Animación de espera de IA
    const typingId = 'ia-typing';
    if (!document.getElementById(typingId)) {
        chatBox.innerHTML += `<div class="chat-typing" id="${typingId}"><b>IA:</b> <span class="dot-typing"><span></span><span></span><span></span></span></div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    try {
        const formData = new FormData();
        formData.append("chatInput", texto);
        formData.append("sessionId", sessionId);
        formData.append("currentPage", currentPage); // ✨ NUEVO: Enviar contexto de página
        formData.append("location", JSON.stringify(detectarUbicacion())); // ✨ NUEVO: Enviar ubicación
        
        if (archivo) {
            formData.append("data00", archivo); 
        }

        const respuesta = await fetch(urlN8N, {
            method: "POST",
            body: formData 
        });

        const datos = await respuesta.json();
        
        // ===== ✨ NUEVA LÓGICA DE PROCESAMIENTO ===== 
        procesarRespuestaIA(datos);
        
        fileInput.value = ""; 
    } catch (error) {
        manejarErrorConexion();
    }
    
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 🧠 NUEVA FUNCIÓN: Procesar diferentes tipos de respuesta de la IA
function procesarRespuestaIA(datos) {
    // Eliminar animación de espera
    const typingDiv = document.getElementById('ia-typing');
    if (typingDiv) typingDiv.remove();

    const chatBox = document.getElementById("chat-box");
    let respuestaIA = datos.output || "Procesado correctamente.";
    const metadata = datos.metadata || {};

    // 📊 CASO 1: Respuesta con gráfico dinámico
    if (metadata.type === "graph_response" && metadata.powerBiUrl) {
        
        // Actualizar URL global de Power BI
        currentPowerBiUrl = metadata.powerBiUrl;
        
        // Buscar si hay enlaces en formato [Texto](URL) y convertirlos
        const respuestaConLinks = respuestaIA.replace(
            /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
            '<a href="$2" target="_blank" class="download-link">$1</a>'
        );

        chatBox.innerHTML += `<div class="message bot-msg"><b>IA:</b> ${respuestaConLinks}</div>`;
        
        // 🎯 AUTO-MOSTRAR el Power BI si se solicita
        if (respuestaIA.includes('[MOSTRAR_GRAFICO]')) {
            // Actualizar el iframe con nueva URL antes de mostrar
            actualizarIframePowerBI(currentPowerBiUrl);
            
            setTimeout(() => {
                togglePowerBI(true); // Mostrar automáticamente
            }, 500); // Pequeño delay para mejor UX
        }
        
    } 
    // 💬 CASO 2: Respuesta normal de IA
    else {
        // Buscar enlaces y convertirlos
        const respuestaConLinks = respuestaIA.replace(
            /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
            '<a href="$2" target="_blank" class="download-link">$1</a>'
        );

        chatBox.innerHTML += `<div class="message bot-msg"><b>IA:</b> ${respuestaConLinks}</div>`;
        
        // Si el texto sugiere mostrar gráfico pero no vino URL, usar la por defecto
        if (respuestaIA.includes('[MOSTRAR_GRAFICO]')) {
            setTimeout(() => {
                togglePowerBI(true);
            }, 500);
        }
    }
}

// 🌍 NUEVA FUNCIÓN: Detectar página actual
function detectarPaginaActual() {
    const pathname = window.location.pathname.toLowerCase();
    
    if (pathname.includes('naval')) return 'naval';
    if (pathname.includes('agro')) return 'agro';
    if (pathname.includes('aereo')) return 'aereo';
    if (pathname.includes('energia')) return 'energia';
    
    // Detectar por título o elementos de la página
    const title = document.title.toLowerCase();
    if (title.includes('naval') || title.includes('command')) return 'naval';
    if (title.includes('agro') || title.includes('intelligence')) return 'agro'; 
    if (title.includes('aereo') || title.includes('aviation')) return 'aereo';
    if (title.includes('energia') || title.includes('energy')) return 'energia';
    
    // Detectar por clases CSS o elementos únicos de cada sector
    if (document.querySelector('.nav-header .brand-text')?.textContent.includes('NAVAL')) return 'naval';
    if (document.querySelector('.nav-header .brand-text')?.textContent.includes('AGRO')) return 'agro';
    if (document.querySelector('.nav-header .brand-text')?.textContent.includes('AVIATION')) return 'aereo';
    if (document.querySelector('.nav-header .brand-text')?.textContent.includes('ENERGY')) return 'energia';
    
    return 'general'; // Por defecto
}

// 📏 NUEVA FUNCIÓN: Detectar ubicación mejorada
function detectarUbicacion() {
    // Intentar extraer de coordenadas en la página (variables template Django)
    const latElement = document.querySelector('[data-lat]');
    const lonElement = document.querySelector('[data-lon]');
    
    if (latElement && lonElement) {
        return {
            lat: parseFloat(latElement.getAttribute('data-lat')),
            lon: parseFloat(lonElement.getAttribute('data-lon')),
            region: "Detectada",
            source: "page_data"
        };
    }
    
    // Buscar en variables globales de Django (si existen)
    if (typeof window.lat !== 'undefined' && typeof window.lon !== 'undefined') {
        return {
            lat: window.lat,
            lon: window.lon,
            region: window.region || "Buenos Aires",
            source: "global_vars"
        };
    }
    
    // Extraer de coordenadas mostradas en pantalla (formato visual)
    const coordsDisplay = document.querySelector('.coords-display, .coordinates');
    if (coordsDisplay) {
        const text = coordsDisplay.textContent;
        const latMatch = text.match(/LAT[:\s]*(-?\d+\.\d+)/i);
        const lonMatch = text.match(/LON[:\s]*(-?\d+\.\d+)/i);
        
        if (latMatch && lonMatch) {
            return {
                lat: parseFloat(latMatch[1]),
                lon: parseFloat(lonMatch[1]),
                region: "Buenos Aires",
                source: "coords_display"
            };
        }
    }
    
    // Ubicación por defecto según sector
    const sector = detectarPaginaActual();
    const defaultLocations = {
        "naval": { lat: -34.5794, lon: -58.5944, region: "Puerto Buenos Aires" },
        "agro": { lat: -32.8895, lon: -60.7842, region: "Zona Agrícola" },
        "aereo": { lat: -34.8222, lon: -58.5358, region: "Aeropuerto Ezeiza" },
        "energia": { lat: -38.0054, lon: -57.5426, region: "Parque Eólico" }
    };
    
    return {
        ...defaultLocations[sector] || defaultLocations.naval,
        source: "default_sector"
    };
}

// 🔄 NUEVA FUNCIÓN: Actualizar iframe de Power BI con URL dinámica
function actualizarIframePowerBI(nuevaUrl) {
    const iframe = document.querySelector('#powerbi-container iframe');
    if (iframe && nuevaUrl) {
        console.log('🔄 Actualizando Power BI con URL:', nuevaUrl);
        iframe.src = nuevaUrl;
    }
}

// 🎨 FUNCIÓN MEJORADA: Toggle Power BI con soporte para URLs dinámicas
function togglePowerBI(forceShow = false) {
    const container = document.getElementById('powerbi-container');
    const chatContainer = document.querySelector('.chat-container');
    
    if (forceShow || container.style.display === 'none') {
        // Si hay URL dinámica, actualizarla antes de mostrar
        if (currentPowerBiUrl) {
            actualizarIframePowerBI(currentPowerBiUrl);
        }
        
        // Mostrar Power BI
        container.style.display = 'block';
        
        // Scroll suave hacia el contenedor
        setTimeout(() => {
            container.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
        
        // 📊 Log para debugging
        console.log('📊 Power BI mostrado con URL:', currentPowerBiUrl || 'URL por defecto');
        
    } else {
        // Ocultar Power BI
        container.style.display = 'none';
        
        // Scroll de regreso al chat
        if (chatContainer) {
            chatContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
    }
}

// 🎯 FUNCIÓN AUXILIAR: Generar icono de archivo
function generarIconoArchivo(archivo) {
    if (!archivo) return '';
    
    let icon = '';
    if (archivo.type.startsWith('image/')) {
        icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>';
    } else if (archivo.type === 'application/pdf') {
        icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><text x="8" y="16" font-size="8" font-weight="bold" fill="currentColor">PDF</text></svg>';
    } else if (archivo.type.includes('excel') || archivo.name.match(/\.(xlsx|xls|csv)$/i)) {
        icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><rect x="7" y="7" width="2" height="2"/><rect x="13" y="7" width="2" height="2"/><rect x="7" y="13" width="2" height="2"/><rect x="13" y="13" width="2" height="2"/></svg>';
    } else {
        icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    }
    return icon;
}

// ⚠️ FUNCIÓN AUXILIAR: Manejar errores de conexión
function manejarErrorConexion() {
    const typingDiv = document.getElementById('ia-typing');
    if (typingDiv) typingDiv.remove();
    
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML += `<div class="message bot-msg" style="color:red;">⚠️ Error de conexión. Intenta nuevamente.</div>`;
}

// 🔧 FUNCIÓN AUXILIAR: Generar UUID (sin cambios)
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        return (c == 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

// 📝 CONFIGURACIÓN DE HISTORIAL (sin cambios)
let historialMensajes = [];
let indiceHistorial = -1;

document.getElementById("user-input").addEventListener("keydown", (e) => {
    const input = e.target;
    if (e.key === "ArrowUp") {
        if (historialMensajes.length > 0 && indiceHistorial < historialMensajes.length - 1) {
            indiceHistorial++;
            input.value = historialMensajes[historialMensajes.length - 1 - indiceHistorial];
        }
        e.preventDefault();
    } else if (e.key === "ArrowDown") {
        if (indiceHistorial > 0) {
            indiceHistorial--;
            input.value = historialMensajes[historialMensajes.length - 1 - indiceHistorial];
        } else {
            indiceHistorial = -1;
            input.value = "";
        }
        e.preventDefault();
    } else if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (input.value.trim() !== "") {
            enviarMensaje();
        }
    }
});

// 📁 GESTIÓN DE ARCHIVOS (sin cambios)
document.getElementById("file-input").addEventListener("change", function() {
    const file = this.files[0];
    const preview = document.getElementById("file-preview");
    if (file) {
        const icon = generarIconoArchivo(file);
        preview.innerHTML = '<span style="display:flex; align-items:center; gap:6px;">' + icon + '<span>' + file.name + '</span></span>';
    } else {
        preview.innerHTML = '';
    }
});

// 🌍 NUEVA FUNCIÓN: Integrar Power BI con N8N
async function enviarSolicitudPowerBI(mensaje, metrica = null) {
    try {
        const sector = detectarPaginaActual();
        const ubicacion = detectarUbicacion();
        
        // 🎯 URLs de tus webhooks N8N ya configurados
        const webhookUrls = {
            'agro': 'https://n8n-production-2651.up.railway.app/webhook/Agro_BI',
            'aereo': 'https://n8n-production-2651.up.railway.app/webhook/Aereo_BI',
            'energia': 'https://n8n-production-2651.up.railway.app/webhook/Energia_BI',
            'naval': 'https://n8n-production-2651.up.railway.app/webhook/Naval_BI'
        };
        
        const webhookUrl = webhookUrls[sector] || webhookUrls['naval'];
        
        console.log('📊 Enviando solicitud Power BI:', { 
            sector: sector,
            webhook: webhookUrl,
            userMessage: mensaje.substring(0, 100) + '...' 
        });
        
        // 📤 Envío directo al webhook N8N del sector
        const response = await fetch(webhookUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chatInput: mensaje,
                currentPage: sector,
                location: {
                    lat: ubicacion.lat,
                    lon: ubicacion.lon,
                    region: ubicacion.region || "Buenos Aires"
                },
                requestType: "power_bi_request",
                sessionId: sessionId,
                timestamp: new Date().toISOString()
            })
        });
        
        const data = await response.json();
        console.log('✅ Respuesta recibida de N8N:', data);
        
        return data;
        
    } catch (error) {
        console.error('❌ Error en solicitud Power BI:', error);
        return { 
            error: 'Error al conectar con el sistema de visualización', 
            output: `❌ Error de conexión con Power BI. Intenta nuevamente.`
        };
    }
}

// 🚀 INICIALIZACIÓN
document.addEventListener("DOMContentLoaded", function() {
    console.log("🚀 TuClima IA Chat con Power BI Dinámico iniciado");
    console.log("📍 Página actual:", detectarPaginaActual());
    console.log("🌍 Ubicación:", detectarUbicacion());
    
    // Configurar sessión con contexto inicial
    const sessionData = {
        page: detectarPaginaActual(),
        location: detectarUbicacion(),
        timestamp: new Date().toISOString()
    };
    
    localStorage.setItem(`session_${sessionId}_context`, JSON.stringify(sessionData));
});

/**
 * 📋 EJEMPLOS DE USO PARA TESTING:
 * 
 * Chat Input: "muéstrame temperatura de hoy"
 * → Debería generar URL con filtros temporales
 * 
 * Chat Input: "comparar viento entre sectores"  
 * → Debería abrir página comparativa de Power BI
 * 
 * Chat Input: "mapa de lluvia en Argentina"
 * → Debería mostrar vista de mapa con precipitación
 * 
 * Chat Input: "pronóstico para mañana"
 * → Debería abrir vista predictiva
 */